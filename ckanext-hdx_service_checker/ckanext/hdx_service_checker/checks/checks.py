
import ckanext.hdx_service_checker.checks as checks
import ckanext.hdx_service_checker.exceptions as exceptions


class DummyCheck(checks.Check):
    type = 'Dummy Check'

    def __init__(self, config, user_agent='SERVICE_CHECKER'):
        super(DummyCheck, self).__init__(config, user_agent)

        self.result = config.get('result') or 'Passed'
        self.error_message = config.get('error_message') or 'Dummy message'
        self.description = config.get('description') or 'Just a dummy check. Does nothing.'

    def run_check(self):
        return super(DummyCheck, self)._create_result()


class HttpStatusCodeCheck(checks.Check):
    '''
    The following config fields should be set:
    {
        "name": "Solr"
        "module_name": "ckanext.hdx_service_checker.checks.checks",
        "class_name": "HttpStatusCodeCheck",
        "url": "http://172.17.42.1:9013/api/status_check",
        "accepted_codes" = "200, 302" //Comma separated list
    }
    '''

    type = 'HTTP Status Check'
    description = 'Makes a request to a specified url and checks the HTTP response code against the accepted_codes'

    def run_check(self):
        url = self.config.get('url')
        accepted_codes = self.config.get('accepted_codes')

        if not url or not accepted_codes:
            raise exceptions.ParamMissingException('Param missing for HttpStatusCodeCheck')

        try:
            r = self._request_get(url)
            status = str(r.status_code)
            if status in accepted_codes:
                self.result = 'Passed'
                self.error_message = ''
            else:
                self.result = 'Failed'
                self.error_message = 'Status code is {} instead of: {}'.format(status, ' or '.join(accepted_codes))
        except Exception as e:
            self.result = 'Failed'
            self.error_message = str(e)

        result = super(HttpStatusCodeCheck, self)._create_result()
        return result


class HttpResponseTextCheck(checks.Check):
    '''
    The following config fields should be set:
    {
        "name": "Solr"
        "module_name": "ckanext.hdx_service_checker.checks.checks",
        "class_name": "HttpResponseTextCheck",
        "url": "http://172.17.42.1:9013/api/status_check",
        "included_text" = "Status is ok"
    }
    '''
    type = 'HTTP Response Text Check'
    description = 'Makes a request to a specified url and checks that the HTTP response contains "included_text"'

    def _basic_auth(self):
        basic_auth = self.config.get('basic_auth')
        if basic_auth and basic_auth != "None":
            headers = {'Authorization': 'Basic {0}'.format(basic_auth)}
            return headers
        return None

    def run_check(self):
        url = self.config.get('url')
        included_text = self.config.get('included_text')

        if not url or not included_text:
            raise exceptions.ParamMissingException('Param missing for HttpStatusCodeCheck')

        try:
            r = self._request_get(url, None, self._basic_auth())

            if included_text in r.text:
                self.result = 'Passed'
                self.error_message = ''
            else:
                self.result = 'Failed'
                self.error_message = '"{}" was not found in HTTP response'.format(included_text)
        except Exception as e:
            self.result = 'Failed'
            self.error_message = str(e)

        result = super(HttpResponseTextCheck, self)._create_result()
        return result


class ProxyForRemoteCheck(checks.Check):
    '''
    The following config fields should be set:
    {
        "name": "GIS LAYER"
        "module_name": "ckanext.hdx_service_checker.checks.checks",
        "class_name": "ProxyForRemoteCheck",
        "url": "http://172.17.42.1:9013/api/status_check",
    }
    '''
    type = 'Proxy for Remote Check'
    description = 'Calls another service which performs its own checks. This check just wraps the result'

    def run_check(self):
        url = self.config.get('url')

        if not url:
            raise exceptions.ParamMissingException('Param missing for HttpStatusCodeCheck')

        try:
            r = self._request_get(url)
            response = r.json()
            if 'result' in response:
                self.subchecks = response['result']
                self.result = 'subchecks'
                self.error_message = ''
            else:
                self.result = 'Failed'
                self.error_message = '"result" field missing from json response'
                self.subchecks = response

        except Exception as e:
            self.result = 'Failed'
            self.error_message = str(e)

        result = super(ProxyForRemoteCheck, self)._create_result()
        return result
