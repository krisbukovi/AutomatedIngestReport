

import requests
import re
from time import sleep
from datetime import datetime
import shutil

# from apiclient.discovery import build
from utils import Filename, FileType, Date, conf, logger


class Gather:
    """gather data from various sources (canonical list, solr, etc.)

    ads files are placed in a while known directory with a name based on date and their contents"""

    def __init__(self, date=Date.TODAY):
        """use passed date as prefix in filenames"""
        self.date = date

    def canonical(self):
        """create local copy of canonical bibcodes"""
        c = conf['CANONICAL_FILE']
        air = Filename.get(self.date, FileType.CANONICAL)
        logger.info('making local copy of canonical bibcodes file, from %s to %s', c, air)
        shutil.copy(c, air)

    def solr(self):
        """use solr batch api to get list of all bibcode it has

        based on http://labs.adsabs.harvard.edu/trac/adsabs/wiki/SearchEngineBatch#Example4:Dumpdocumetsbyquery"""

        url = conf.get('SOLR_URL', 'http://localhost:9983/solr/collection1/')
        # query = 'batch?command=dump-docs-by-query&q=*:*&fl=bibcode&wt=json'
        query = 'batch?command=dump-docs-by-query&q=bibcode:2003ASPC..295..361M&fl=bibcode&wt=json'
        start = 'batch?command=start&wt=json'
        status = 'batch?command=status&wt=json&jobid='
        get_results = 'batch?command=get-results&wt=json&jobid='

        logger.info('sending initial batch query to solr at %s', url)
        rQuery = requests.get(url + query)
        if rQuery.status_code != 200:
            logger.error('initial batch solr query failed, status: %s, text: %s', 
                         rQuery.status_code, rQuery.text)
            return False
        j = rQuery.json()
        jobid = j['jobid']

        logger.info('sending solr start batch command')
        rStart = requests.get(url + start)
        if rStart.status_code != 200:
            logger.error('solr start batch processing failed, status %s, text: %s',
                         rStart.status_code, rStart.text)
            return False

        # now we wait for solr to process batch query
        finished = False
        startTime = datetime.now()
        while not finished:
            rStatus = requests.get(url + status + jobid)
            if rStatus.status_code != 200:
                logger.error('batch status check failed, status: %s, text: %s',
                             rStatus.status_code, rStatus.text)
                return False
            j = rStatus.json()
            if j['job-status'] == 'finished':
                finished = True
            else:
                sleep(10)
            if (datetime.now() - startTime).total_seconds() > 3600 * 2:
                logger.error('solr batch process taking too long, seconds: %s;', 
                             (datetime.now() - startTime).total_seconds())
                return False

        logger.info('solr bacth completed in %s seconds, now fetching bibcodes', 
                    (datetime.now() - startTime).total_seconds())
        rResults = requests.get(url + get_results + jobid)
        if rResults.status_code != 200:
            logger.error('failed to obtain bibcodes from solr batch query, status: %s, text: %s,',
                         rResults.status_code, rResults.text)
            return False

        # finally save bibcodes to file
        bibs = rResults.text  # all 12 million bibcodes are in this one text field
        # convert to json-ish text to simple string, response includes newlines between bibcodes
        bibs = re.sub(r'{"bibcode":"|,|"}', '', bibs)
        filename = Filename.get(self.date, FileType.SOLR)
        with open(filename, 'w') as f:
            f.write(bibs)

        return True