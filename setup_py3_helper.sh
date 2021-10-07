#!/bin/bash

mv -f requirements-py2.txt requirements-py2-tmp.txt
grep -v "github" requirements-py2-tmp.txt >> requirements-py2.txt
mv -f requirements.txt requirements-tmp.txt
grep -v "github" requirements-tmp.txt >> requirements.txt
python setup.py develop
mv -f requirements-py2-tmp.txt requirements-py2.txt
mv -f requirements-tmp.txt requirements.txt

plugins="hdx_service_checker sitemap ytp-request hdx_dataviz hdx_pages"
for p in $plugins; do cd /srv/ckan/ckanext-$p || exit; python setup.py develop; done
cd /srv/ckan || exit

