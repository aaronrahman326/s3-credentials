from click.testing import CliRunner
from s3_credentials.cli import cli
import json
import pytest
from unittest.mock import call, Mock


def test_whoami(mocker):
    boto3 = mocker.patch("boto3.client")
    boto3().get_user.return_value = {"User": {"username": "name"}}
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["whoami"])
        assert result.exit_code == 0
        assert json.loads(result.output) == {"username": "name"}


@pytest.mark.parametrize(
    "option,expected",
    (
        ("", '{\n    "name": "one"\n}\n{\n    "name": "two"\n}\n'),
        (
            "--array",
            '[\n    {\n        "name": "one"\n    },\n'
            '    {\n        "name": "two"\n    }\n]\n',
        ),
        ("--nl", '{"name": "one"}\n{"name": "two"}\n'),
    ),
)
def test_list_users(mocker, option, expected):
    boto3 = mocker.patch("boto3.client")
    boto3().get_paginator().paginate.return_value = [
        {"Users": [{"name": "one"}, {"name": "two"}]}
    ]
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["list-users"] + ([option] if option else []))
        assert result.exit_code == 0
        assert result.output == expected


def test_create(mocker):
    boto3 = mocker.patch("boto3.client")
    boto3.return_value = Mock()
    boto3.return_value.create_access_key.return_value = {
        "AccessKey": {
            "AccessKeyId": "access",
            "SecretAccessKey": "secret",
        }
    }
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["create", "pytest-bucket-simonw-1", "-c"])
        assert result.exit_code == 0
        assert result.output == (
            "Attached policy s3.read-write.pytest-bucket-simonw-1 to user s3.read-write.pytest-bucket-simonw-1\n"
            "Created access key for user: s3.read-write.pytest-bucket-simonw-1\n"
            '{\n    "AccessKeyId": "access",\n    "SecretAccessKey": "secret"\n}\n'
        )
        assert [str(c) for c in boto3.mock_calls] == [
            "call('s3')",
            "call('iam')",
            "call().head_bucket(Bucket='pytest-bucket-simonw-1')",
            "call().get_user(UserName='s3.read-write.pytest-bucket-simonw-1')",
            'call().put_user_policy(PolicyDocument=\'{"Version": "2012-10-17", "Statement": [{"Sid": "ListObjectsInBucket", "Effect": "Allow", "Action": ["s3:ListBucket"], "Resource": ["arn:aws:s3:::pytest-bucket-simonw-1"]}, {"Sid": "AllObjectActions", "Effect": "Allow", "Action": "s3:*Object", "Resource": ["arn:aws:s3:::pytest-bucket-simonw-1/*"]}]}\', PolicyName=\'s3.read-write.pytest-bucket-simonw-1\', UserName=\'s3.read-write.pytest-bucket-simonw-1\')',
            "call().create_access_key(UserName='s3.read-write.pytest-bucket-simonw-1')",
        ]


def test_list_user_policies(mocker):
    boto3 = mocker.patch("boto3.client")
    boto3.return_value = Mock()
    boto3.return_value.get_user_policy.return_value = {
        "PolicyDocument": {"policy": "here"}
    }

    def get_paginator(type):
        m = Mock()
        if type == "list_users":
            m.paginate.return_value = [
                {"Users": [{"UserName": "one"}, {"UserName": "two"}]}
            ]
        elif type == "list_user_policies":
            m.paginate.return_value = [{"PolicyNames": ["policy-one", "policy-two"]}]
        return m

    boto3().get_paginator.side_effect = get_paginator
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["list-user-policies"], catch_exceptions=False)
        assert result.exit_code == 0
        assert result.output == (
            "User: one\n"
            "PolicyName: policy-one\n"
            "{\n"
            '    "policy": "here"\n'
            "}\n"
            "PolicyName: policy-two\n"
            "{\n"
            '    "policy": "here"\n'
            "}\n"
            "User: two\n"
            "PolicyName: policy-one\n"
            "{\n"
            '    "policy": "here"\n'
            "}\n"
            "PolicyName: policy-two\n"
            "{\n"
            '    "policy": "here"\n'
            "}\n"
        )
        assert boto3.mock_calls == [
            call(),
            call("iam"),
            call().get_paginator("list_users"),
            call().get_paginator("list_user_policies"),
            call().get_user_policy(UserName="one", PolicyName="policy-one"),
            call().get_user_policy(UserName="one", PolicyName="policy-two"),
            call().get_user_policy(UserName="two", PolicyName="policy-one"),
            call().get_user_policy(UserName="two", PolicyName="policy-two"),
        ]
