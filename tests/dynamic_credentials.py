"""Tiny stand-in for Muse's dynamic_credentials helper (tests only)."""
import json
import urllib.parse


class DynamicCredentialError(Exception):
    pass


def dynamic_credential_entry(name):
    if name != "custom.telegram":
        raise DynamicCredentialError("no such credential")
    return {"placement": {"url_path_segment": "/bot{}"},
            "surrogate": "hsurr:abc123:def456"}


def ensure_allowed_url(url, hosts):
    host = urllib.parse.urlsplit(url).hostname
    if host not in hosts:
        raise DynamicCredentialError("host not allowed")


def read_json_response(resp):
    return json.loads(resp.read().decode("utf-8"))


def url_with_surrogate_path_segment(template, name, allowed_hosts=()):
    # mimics the buggy upstream helper: percent-encodes the colon
    return template.format(urllib.parse.quote("hsurr:abc123:def456", safe=""))
