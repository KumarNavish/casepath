"""Two independent compatibility/failure checks beyond durable writer cases."""
import socket
import unittest
from unittest.mock import Mock, patch

import httpcore

from casepath_api import hosted_sql_v1 as sql
from test_hosted_idle_transport_v1 import _shared, _SELECT


class IndependentIdleTransportTests(unittest.TestCase):
    def test_fresh_connect_failure_is_not_retried_and_poisoned_connection_cannot_resend(self):
        with patch.object(socket, 'socket', side_effect=AssertionError('Unexpected real socket')), _shared() as h:
            attempts = []
            def failed_connect(**kwargs):
                attempts.append(kwargs)
                raise httpcore.ConnectError('Synthetic connection failure')
            h.backend.connect_tcp = failed_connect
            connection = h.db.connect()
            with self.assertLogs(sql._LOG, level='WARNING'), self.assertRaises(sql.HostedStorageError):
                connection.read_snapshot(_SELECT)
            self.assertTrue(connection._poisoned)
            self.assertEqual(len(attempts), 1)
            self.assertEqual(attempts[0]['timeout'], 3)
            self.assertEqual(h.backend.requests, [])
            with self.assertRaises(sql.HostedStorageError):
                connection.read_snapshot(_SELECT)
            self.assertEqual(len(attempts), 1)
            connection.close()

    def test_nonshared_injected_factory_still_called_without_arguments_and_each_client_owned_once(self):
        with patch.object(socket, 'socket', side_effect=AssertionError('Unexpected real socket')):
            first, second = sql._http_client(), sql._http_client()
            self.assertEqual(first._transport._pool._keepalive_expiry, 30)
            self.assertEqual(second._transport._pool._keepalive_expiry, 30)
            with patch.object(first, 'close', wraps=first.close) as first_close, \
                    patch.object(second, 'close', wraps=second.close) as second_close:
                factory = Mock(side_effect=[first, second])
                database = sql.TursoDatabase('libsql://fixture.invalid', 'fictional-independent-token-' * 2,
                                             client_factory=factory, reuse_http=False)
                try:
                    factory.assert_not_called()
                    self.assertIsNone(database._shared_client)
                    for expected in (first, second):
                        with database.connect() as connection:
                            self.assertIs(connection._client, expected)
                        self.assertTrue(expected.is_closed)
                    self.assertEqual(factory.call_args_list, [unittest.mock.call(), unittest.mock.call()])
                finally:
                    database.close()
                    database.close()
                first_close.assert_called_once_with()
                second_close.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
