import json
import unittest

from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException


class Response(object):
    def __init__(self, data):
        self.data = data

    def getheader(self, name):
        return 'application/json'

    def read(self):
        return json.dumps(self.data).encode('utf8')


class Connection(object):
    def __init__(self, transform):
        self.transform = transform
        self.calls = []

    def request(self, method, path, data, headers):
        self.calls = json.loads(data)

    def getresponse(self):
        responses = [
            {'id': call['id'], 'error': None, 'result': call['params'][0]}
            for call in self.calls
        ]
        return Response(self.transform(responses))


class BatchTest(unittest.TestCase):
    def proxy(self, transform):
        return AuthServiceProxy('http://user:password@localhost:8332',
                                connection=Connection(transform))

    def calls(self):
        return [['echo', 'first'], ['echo', 'second'], ['echo', 'third']]

    def test_reversed_responses_keep_request_order(self):
        proxy = self.proxy(lambda responses: responses[::-1])
        self.assertEqual(proxy.batch_(self.calls()), ['first', 'second', 'third'])
        self.assertEqual(proxy.batch_(self.calls()), ['first', 'second', 'third'])

    def test_ordered_responses(self):
        proxy = self.proxy(lambda responses: responses)
        self.assertEqual(proxy.batch_(self.calls()), ['first', 'second', 'third'])

    def test_rpc_error_is_preserved(self):
        def error_response(responses):
            responses[1] = {'id': responses[1]['id'],
                            'error': {'code': -32601, 'message': 'Method not found'}}
            return responses[::-1]
        with self.assertRaises(JSONRPCException) as raised:
            self.proxy(error_response).batch_(self.calls())
        self.assertEqual(raised.exception.code, -32601)

    def test_missing_result_is_rejected(self):
        def missing_result(responses):
            del responses[0]['result']
            return responses
        with self.assertRaises(JSONRPCException) as raised:
            self.proxy(missing_result).batch_(self.calls())
        self.assertEqual(raised.exception.code, -343)

    def test_missing_response_is_rejected(self):
        with self.assertRaises(JSONRPCException) as raised:
            self.proxy(lambda responses: responses[:-1]).batch_(self.calls())
        self.assertEqual(raised.exception.code, -343)

    def test_duplicate_response_is_rejected(self):
        with self.assertRaises(JSONRPCException) as raised:
            self.proxy(lambda responses: responses + responses[:1]).batch_(self.calls())
        self.assertEqual(raised.exception.code, -343)

    def test_unexpected_response_id_is_rejected(self):
        def unexpected_id(responses):
            responses[0]['id'] = 'unexpected'
            return responses
        with self.assertRaises(JSONRPCException) as raised:
            self.proxy(unexpected_id).batch_(self.calls())
        self.assertEqual(raised.exception.code, -343)

    def test_missing_response_id_is_rejected(self):
        def missing_id(responses):
            del responses[0]['id']
            return responses
        with self.assertRaises(JSONRPCException) as raised:
            self.proxy(missing_id).batch_(self.calls())
        self.assertEqual(raised.exception.code, -343)

    def test_unhashable_response_id_is_rejected(self):
        def invalid_id(responses):
            responses[0]['id'] = []
            return responses
        with self.assertRaises(JSONRPCException) as raised:
            self.proxy(invalid_id).batch_(self.calls())
        self.assertEqual(raised.exception.code, -343)

    def test_batch_level_error_is_preserved(self):
        def batch_error(responses):
            return {'id': None,
                    'error': {'code': -32600, 'message': 'Invalid Request'}}
        with self.assertRaises(JSONRPCException) as raised:
            self.proxy(batch_error).batch_(self.calls())
        self.assertEqual(raised.exception.code, -32600)


if __name__ == '__main__':
    unittest.main()
