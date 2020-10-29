"""
Copyright (c) 2020 Sam Hume

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import requests
import os
import json
import logging
import argparse
import datetime
import xmltodict

# name of the file to capture the visited urls to prevent multiple visits
TESTED_URLS_FILE = "tested_urls.txt"

class LinkCrawler:
    """
    CDISC Library link crawler for caching API responses recursively visits urls to cache standards content. Note, the
    tested urls previously loaded are maintained in the TESTED_URLS_FILE. Use this file to initiate consecutive runs
    without revisiting the same URLs. This file should be empty if starting fresh.
    """
    def __init__(self, args):
        """
        :param args: object containing the argparse CLI arguments - documented in set_cmd_line_args()
        """
        self.base_url = args.base_url
        self.resource = args.start_resource
        self.headers = {"Accept": args.media_type, "api-key": args.api_key}
        self.verbose = args.verbose
        self.log_path = args.log_path
        log_file_name = os.path.join(args.log_path, args.log_file)
        self.logger = self._setup_logging(log_file_name)
        self.tested_urls = set()
        self._load_tested_urls()        # load previously visited urls - clear this file if starting fresh
        self.urls = set()
        self.urls.add(self.resource)
        self.template_variables = ["$_url"]
        self.filters = self._load_filters(args.filter, args.log_path)

    def cache_api_resources(self):
        """
        initiated with the starting url (API resource) and crawls all previously unseen hrefs found that pass the filters
        """
        while self.urls:
            resource = self.urls.pop()
            request_time = datetime.datetime.now()
            self.logger.info(f"Requested: {request_time.strftime('%m/%d/%Y, %H:%M:%S')} - {resource}")
            r = requests.get(self.base_url + resource, headers=self.headers)
            self.tested_urls.add(resource)
            if r.status_code == 200:
                self.logger.info(f"Received: {str(datetime.datetime.now() - request_time).split('.')[0]} - {resource}")
                self._get_links(r.text)
            else:
                self.logger.error(f"Error: {str(r.status_code)} for {resource}")
        self._save_tested_urls()

    def _get_links(self, content):
        """
        adds href urls found in CDISC Library content into url list to retrieve if passed filter and not already retrieved
        :param content: metadata retrieved from the CDISC Library API
        """
        content_dict = self._create_dict_from_content(content)
        for url in self._link_finder(content_dict, "href"):
            if self._passes_primer_filter(url):
                self.urls.add(url)
                # certain HATEOAS was removed from the CT API responses to improve performance
                if "/ct/" in url and "codelist" not in url and url != "/mdr/ct/packages":
                    self.urls.add(url + "/codelists")
            else:
                if self.verbose:
                    self.logger.info(f"Skipping: {url}")
        self.urls.difference_update(self.tested_urls)

    def _passes_primer_filter(self, url):
        """
        determine if the current url passes the filter which indicates it will be used to retrieve content
        :param url: the URL to test
        :return: boolean that indicates whether or not to GET the content from the CDISC Library using the URL
        """
        is_pass_filter = False
        replacements = [url]
        for filter in self.filters:
            final_filter = self._process_string(filter, replacements)
            is_pass_filter = eval(final_filter)
            if is_pass_filter:
                break
        return is_pass_filter

    def _process_string(self, item, replacements):
        """
        replace variables in template filter strings (e.g. replace $_url with the current url)
        :param item: the template filter string with the variables
        :param replacements: values that replace the variables
        :return: the updated string with all variables replaced with values
        """
        updated_item = item
        for variable, replacement in zip(self.template_variables, replacements):
            # assumes that we're always replacing the template variable with a literal string
            updated_item = updated_item.replace(variable, "\"" + replacement + "\"")
        return updated_item

    def _create_dict_from_content(self, content):
        """
        content is retrieved from the CDISC Library in different media types but we use JSON to find urls
        :param content: metadata retrieved from the CDISC Library using different media types
        :return: dictionary containing CDISC Library content (and converted from original format)
        """
        if "json" in self.headers["Accept"]:
            content_dict = json.loads(content)
        elif "xml" in self.headers["Accept"]:
            content_dict = xmltodict.parse(content)
        elif "vnd.ms-excel" in self.headers["Accept"] or "text/csv" in self.headers["Accept"]:
            content_dict = {}
        else:
            raise ValueError("Unknown media type: " + self.headers["Accept"])
        return content_dict

    def _link_finder(self, json_input, lookup_key):
        """
        generator that creates a lazy recursion to find a key ("href") in JSON formatted API content
        :param json_input: CDISC Library API content formatted as JSON (other media types converted to JSON)
        :param lookup_key: url (link) identifier to find in the json_input - this is "href" in the CDISC Library
        :return: yields a url (a link)
        """
        if isinstance(json_input, dict):
             for k, v in json_input.items():
                if k == lookup_key:
                    yield v
                else:
                    yield from self._link_finder(v, lookup_key)
        elif isinstance(json_input, list):
            for item in json_input:
                yield from self._link_finder(item, lookup_key)

    def _setup_logging(self, log_file_name):
        """
        setup both console and file logging to track the results of the link crawler
        :param log_file_name: name of the file to write the logging info to
        :return: ready to use logger object
        """
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        fileHandler = logging.FileHandler(log_file_name)
        logger.addHandler(fileHandler)
        consoleHandler = logging.StreamHandler()
        logger.addHandler(consoleHandler)
        return logger

    @staticmethod
    def _load_filters(filename, log_path):
        """
        load filters from a text file - filters identify what content is requested with everything else filtered out
        :param filename: name of the file that contains the filters - prevent link crawler from crawling everything
        :param log_path: filters are maintained in the same path as the output logs
        :return: list of filters loaded from filter text file (one per line)
        """
        filter_file_name = os.path.join(log_path, filename)
        with open(filter_file_name, "r", encoding="utf-8") as filter:
            filters = filter.read().splitlines()
        return filters

    def _load_tested_urls(self):
        """
        load the already visited urls (links) from a text file to skip re-loading them.
        """
        tested_urls_file_name = os.path.join(self.log_path, TESTED_URLS_FILE)
        try:
            with open(tested_urls_file_name, "r", encoding="utf-8") as urls:
                self.tested_urls = set(urls.read().splitlines())
            self.logger.info(f"Loaded {len(self.tested_urls)} previously tested URLs from {TESTED_URLS_FILE}")
        except:
            self.logger.info(f"No previously tested URLs loaded from {TESTED_URLS_FILE}.")

    def _save_tested_urls(self):
        """
        write the urls (links) that have been visited to a file so that they are not re-visited
        """
        # TODO add feature to include media type with url as the same url is loaded for multiple media types
        tested_urls_file_name = os.path.join(self.log_path, TESTED_URLS_FILE)
        with open(tested_urls_file_name, "w", encoding="utf-8") as urls:
            for url in self.tested_urls:
                urls.write(url + "\n")


def set_cmd_line_args():
    """
    command-line arguments - set defaults to something convenient to simplify launching
    e.g. -r /mdr/ct/packages -a e9a7d1b9bf1a4036ae7b123456081565 -b https://library.cdisc.org/api -m application/json
    qa e.g. -r /mdr/ct/packages -b https://cdisc-mdsp-qa.nurocorcloud.com/api -m application/json -a e9a7d1b9bf1a4036ae7b123456081565
    -r /mdr/sdtm/1-8 -b https://cdisc-mdsp-qa.nurocorcloud.com/api -m application/json -a e9a7d1b9bf1a4036ae7b123456081565
    -r /mdr/sdtm/1-8 -b https://library.cdisc.org/api -m application/json -a e9a7d1b9bf1a4036ae7b123456081565 -f prime_cache_filters.txt
    """
    data_path = os.path.dirname(os.path.realpath(__file__))
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--api_key", help="API Key", dest="api_key", required=True)
    parser.add_argument("-b", "--base_url", dest="base_url", help="Library API base URL", default="https://library.cdisc.org/api")
    parser.add_argument("-r", "--resource", dest="start_resource", help="Library API resource", default="/mdr/ct/packages")
    parser.add_argument("-l", "--log_file", help="log file name", default="link_log.txt", dest="log_file")
    parser.add_argument("-d", "--log_dir", help="path to log and config file directory", default=data_path, dest="log_path")
    parser.add_argument("-m", "--media_type", help="media_type", default="application/json", dest="media_type")
    parser.add_argument("-v", "--verbose", dest="verbose", help="verbose", default=False, required=False)
    parser.add_argument("-f", "--filter", help="filter file name", default="prime_cache_filters.txt", dest="filter")
    args = parser.parse_args()
    return args


def main():
    """
    main method that drives the LinkCrawler to perform CDISC cache priming
    """
    args = set_cmd_line_args()
    ln = LinkCrawler(args)
    ln.cache_api_resources()


if __name__ == "__main__":
    main()