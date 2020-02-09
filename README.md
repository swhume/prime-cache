# PrimeCache

## Introduction
This repository contains the prime_cache.py program created to help cache CDISC Library
content to obviate the performance issues for certain non-cached content.

## Getting Started
prime-cache.py is the only program file. It uses a command-line interface.

Command-line parameters include:
* -r is the starting resource
* -b is the base url
* -m is the media-type (application/json is the default)
* -u is the username
* -p is the password
* -f is the filter file (after the starting resource only those that pass the filter are requested)

The filter restricts those API URLs that will be requested by the program. A filter consists
one or more lines of templated code, such as:
* "sdtm/1-8" in $_url

Or, an example of controlled terminology filters include:
* ($_url == "/mdr/ct/packages")
* ("/ct/" in $_url) and ("terms" not in $_url) and ("2019-09-27" in $_url or "root" in $_url)

## CLI Examples
* prime_cache -r /mdr/sdtm/1-8 -b https://library.cdisc.org/api -m application/json -u shume@cdisc.org -p password -f prime_cache_filters.txt

* prime_cache -r /mdr/sdtmig/3-1-2 -b https://library.cdisc.org/api -m application/json -u shume@cdisc.org -p password -f filter_sdtmig.txt

## Important Usage Notes
* Start with an empty tested_urls.txt to retrieve all API resources (URLs) that pass the filters

* Keep the tested_urls.txt from a previous run to not re-load those URLs already cached

* Filters determine which URLs are retrieved meaning any URL that matches one of the filters listed
in the text file will be retrieved if not already in the tested_urls.txt file

* The same URLs may be requested more than once to account for different media types

## Future Enhancements
Since we now cache multiple media types per API resource, or URL, we should add the media
type to the URL in the tested_urls.txt so that we don't need to clear out the tested_urls.txt
file and re-run the link crawler for additional media types.





