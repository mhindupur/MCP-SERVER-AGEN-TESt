from __future__ import annotations

from dataclasses import dataclass

import boto3


@dataclass(frozen=True)
class AwsTemporaryCredentials:
    access_key_id: str
    secret_access_key: str
    session_token: str


def assume_role(*, role_arn: str, session_name: str, external_id: str | None = None) -> AwsTemporaryCredentials:
    sts = boto3.client("sts")
    kwargs = {"RoleArn": role_arn, "RoleSessionName": session_name}
    if external_id:
        kwargs["ExternalId"] = external_id
    resp = sts.assume_role(**kwargs)
    creds = resp["Credentials"]
    return AwsTemporaryCredentials(
        access_key_id=creds["AccessKeyId"],
        secret_access_key=creds["SecretAccessKey"],
        session_token=creds["SessionToken"],
    )
