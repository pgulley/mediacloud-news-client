import datetime as dt
from typing import List, Dict
import requests
import logging
import ciso8601

VERSION = "v1"  # the API access URL is versioned for future compatability and maintenance


class SearchApiClient:

    API_BASE_URL = "http://colsearch.sawood-dev.us.archive.org:8000/{}/".format(VERSION)

    TERM_FIELD_TITLE = "title"
    TERM_FIELD_SNIPPET = "snippet"
    TERM_AGGREGATION_TOP = "top"
    TERM_AGGREGATION_SIGNIFICANT = "significant"
    TERM_AGGREGATION_RARE = "rare"

    def __init__(self, collection):
        self._collection = collection
        self._logger = logging.getLogger(__name__)

    def sample(self, query: str, start_date: dt.datetime, end_date: dt.datetime, **kwargs) -> List[Dict]:
        results = self._overview_query(query, start_date, end_date, **kwargs)
        if self._is_no_results(results):
            return []
        return results['matches']

    def top_sources(self, query: str, start_date: dt.datetime, end_date: dt.datetime, **kwargs) -> List[Dict]:
        results = self._overview_query(query, start_date, end_date, **kwargs)
        if self._is_no_results(results):
            return []
        return self._dict_to_list(results['topdomains'])

    def top_tlds(self, query: str, start_date: dt.datetime, end_date: dt.datetime, **kwargs) -> List[Dict]:
        results = self._overview_query(query, start_date, end_date, **kwargs)
        if self._is_no_results(results):
            return []
        return self._dict_to_list(results['toptlds'])

    def top_languages(self, query: str, start_date: dt.datetime, end_date: dt.datetime, **kwargs) -> List[Dict]:
        results = self._overview_query(query, start_date, end_date, **kwargs)
        if self._is_no_results(results):
            return []
        return self._dict_to_list(results['toplangs'])

    @staticmethod
    def _is_no_results(results: Dict) -> bool:
        return ('matches' not in results) and ('detail' in results) and (results['detail'] == 'No results found!')

    def count(self, query: str, start_date: dt.datetime, end_date: dt.datetime, **kwargs) -> int:
        results = self._overview_query(query, start_date, end_date, **kwargs)
        if self._is_no_results(results):
            return 0
        return results['total']

    def count_over_time(self, query: str, start_date: dt.datetime, end_date: dt.datetime, **kwargs) -> Dict:
        results = self._overview_query(query, start_date, end_date, **kwargs)
        if self._is_no_results(results):
            return {}
        data = results['dailycounts']
        to_return = []
        for day_date, day_value in data.items():  # date is in 'YYYY-MM-DD' format
            day = ciso8601.parse_datetime(day_date)
            to_return.append({
                'date': day,
                'timestamp': day.timestamp(),
                'count': day_value,
            })
        return {'counts': to_return}

    @staticmethod
    def _date_query_clause(start_date: dt.datetime, end_date: dt.datetime) -> str:
        return "publication_date:[{} TO {}]".format(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))

    def _overview_query(self, query: str, start_date: dt.datetime, end_date: dt.datetime, **kwargs) -> Dict:
        params = {"q": "{} AND {}".format(query, self._date_query_clause(start_date, end_date))}
        params.update(kwargs)
        results, response = self._query("{}/search/overview".format(self._collection), params, method='POST')
        return results

    def item(self, item_id: str) -> Dict:
        results, _ = self._query("{}/article/{}".format(self._collection, item_id), method='GET')
        return results

    def all_items(self, query: str, start_date: dt.datetime, end_date: dt.datetime, page_size: int = 1000,  **kwargs):
        params = {"q": "{} AND {}".format(query, self._date_query_clause(start_date, end_date))}
        params.update(kwargs)
        more_pages = True
        while more_pages:
            page, response = self._query("{}/search/result".format(self._collection), params, method='POST')
            yield page
            # check if there is a link to the next page
            more_pages = False
            next_link_token = response.headers.get('x-resume-token')
            if next_link_token:
                params['resume'] = next_link_token
                more_pages = True

    def terms(self, query: str, start_date: dt.datetime, end_date: dt.datetime, field: str, aggregation: str, **kwargs) -> Dict:
        params = {"q": "{} AND {}".format(query, self._date_query_clause(start_date, end_date))}
        params.update(kwargs)
        results, response = self._query("{}/terms/{}/{}".format(self._collection, field, aggregation), params,
                                        method='GET')
        return results

    def _query(self, endpoint: str, params: Dict = None, method: str = 'GET'):
        """
        Centralize making the actual queries here for easy maintenance and testing of HTTP comms
        """
        endpoint_url = self.API_BASE_URL+endpoint
        if method == 'GET':
            r = requests.get(endpoint_url, params)
        elif method == 'POST':
            r = requests.post(endpoint_url, json=params)
        else:
            raise RuntimeError("Unsupported method of '{}'".format(method))
        return r.json(), r

    @classmethod
    def _dict_to_list(cls, data: Dict) -> List[Dict]:
        """
        The API returns dicts, but that isn't very restful nor the current standard apporach to user-friendly JSON.
        This utility method converts tht into a list of dicts.
        """
        return [{'name': k, 'value': v} for k, v in data.items()]
