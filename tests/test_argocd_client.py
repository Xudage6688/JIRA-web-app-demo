"""
ArgoCD Client SSL Verification Tests
"""

import os
import pytest
from unittest.mock import patch, MagicMock


class TestArgocdSslVerify:
    """Tests for ARGOCD_SSL_VERIFY environment variable configuration"""

    def test_ssl_verify_default_true(self):
        """Test that default behavior verified SSL (verify=True)"""
        # Clear env var if it exists
        env_backup = os.environ.pop('ARGOCD_SSL_VERIFY', None)

        try:
            from modules.argocd_client import ArgoCDClient

            # Mock requests.get to capture the verify parameter
            with patch('modules.argocd_client.requests.get') as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {}
                mock_get.return_value = mock_response

                client = ArgoCDClient('preprod', 'test-token')
                client.get_application('test-app')

                # Verify that requests.get was called with verify=True (default)
                mock_get.assert_called_once()
                call_kwargs = mock_get.call_args[1]
                assert call_kwargs.get('verify') is True, "Default verify should be True"
        finally:
            # Restore env var
            if env_backup is not None:
                os.environ['ARGOCD_SSL_VERIFY'] = env_backup

    def test_ssl_verify_disabled_via_env_var(self):
        """Test that SSL verification can be disabled via ARGOCD_SSL_VERIFY=False"""
        # Set env var to disable SSL verification
        os.environ['ARGOCD_SSL_VERIFY'] = 'False'

        try:
            from modules.argocd_client import ArgoCDClient

            # Mock requests.get to capture the verify parameter
            with patch('modules.argocd_client.requests.get') as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {}
                mock_get.return_value = mock_response

                client = ArgoCDClient('preprod', 'test-token')
                client.get_application('test-app')

                # Verify that requests.get was called with verify=False
                mock_get.assert_called_once()
                call_kwargs = mock_get.call_args[1]
                assert call_kwargs.get('verify') is False, "verify should be False when ARGOCD_SSL_VERIFY=False"
        finally:
            # Clean up env var
            os.environ.pop('ARGOCD_SSL_VERIFY', None)

    def test_ssl_verify_explicit_true(self):
        """Test that ARGOCD_SSL_VERIFY=True enables SSL verification"""
        os.environ['ARGOCD_SSL_VERIFY'] = 'True'

        try:
            from modules.argocd_client import ArgoCDClient

            with patch('modules.argocd_client.requests.get') as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {}
                mock_get.return_value = mock_response

                client = ArgoCDClient('preprod', 'test-token')
                client.get_application('test-app')

                call_kwargs = mock_get.call_args[1]
                assert call_kwargs.get('verify') is True, "verify should be True when ARGOCD_SSL_VERIFY=True"
        finally:
            os.environ.pop('ARGOCD_SSL_VERIFY', None)

    def test_ssl_verify_get_manifests(self):
        """Test that get_manifests also respects SSL verification setting"""
        os.environ['ARGOCD_SSL_VERIFY'] = 'False'

        try:
            from modules.argocd_client import ArgoCDClient

            with patch('modules.argocd_client.requests.get') as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"manifests": []}
                mock_get.return_value = mock_response

                client = ArgoCDClient('preprod', 'test-token')
                # get_manifests first calls get_application via get_app_revision
                with patch.object(client, 'get_app_revision', return_value='abc123'):
                    client.get_manifests('test-app', 'abc123')

                # Verify the second call (get_manifests) uses correct verify setting
                call_kwargs = mock_get.call_args[1]
                assert call_kwargs.get('verify') is False, "get_manifests should use verify=False when disabled"
        finally:
            os.environ.pop('ARGOCD_SSL_VERIFY', None)