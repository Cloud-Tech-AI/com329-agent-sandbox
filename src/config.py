"""App settings.

Sources, highest priority first:
1. Environment variables (also what `envFrom: secretRef` sets in a pod)
2. `.env` file in the working directory (local development)
3. Files in SECRETS_DIR, one file per setting (a Kubernetes Secret mounted as a volume)
4. Defaults below
"""

import os
from functools import lru_cache
from pathlib import Path

import boto3
from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Where the Kubernetes Secret is mounted in the pod; see k8s/deployment.yaml
SECRETS_DIR = Path(os.getenv("SECRETS_DIR", "/etc/code-change-agent/secrets"))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # only point at the secrets dir when it exists, so local runs don't warn
        secrets_dir=SECRETS_DIR if SECRETS_DIR.is_dir() else None,
        case_sensitive=False,
        # treat `AWS_PROFILE=` (blank, as in .env.example) as unset
        env_ignore_empty=True,
        extra="ignore",
    )

    @model_validator(mode="before")
    @classmethod
    def _drop_blank_values(cls, data: dict) -> dict:
        # env_ignore_empty only covers environment variables. Blank values from .env or from
        # secret files (e.g. `kubectl create secret --from-env-file=.env` with `AWS_PROFILE=`)
        # would otherwise override defaults and the AWS credential chain, so treat them as unset.
        return {
            key: value
            for key, value in data.items()
            if not (isinstance(value, str) and not value.strip())
        }

    aws_region: str = "us-east-1"
    model_id: str = "global.anthropic.claude-sonnet-4-6"

    # Optional static credentials. Leave unset to use the default AWS chain
    # (AWS_PROFILE, ~/.aws, or IRSA / EKS Pod Identity in the cluster).
    aws_profile: str | None = None
    aws_access_key_id: SecretStr | None = None
    aws_secret_access_key: SecretStr | None = None
    aws_session_token: SecretStr | None = None

    # GitHub personal access token (repo scope) used to open pull requests
    github_token: SecretStr | None = None
    github_api_url: str = "https://api.github.com"

    def boto_session(self) -> boto3.Session:
        def reveal(value: SecretStr | None) -> str | None:
            return value.get_secret_value() if value else None

        if self.aws_access_key_id and self.aws_secret_access_key:
            return boto3.Session(
                aws_access_key_id=reveal(self.aws_access_key_id),
                aws_secret_access_key=reveal(self.aws_secret_access_key),
                aws_session_token=reveal(self.aws_session_token),
                region_name=self.aws_region,
            )
        return boto3.Session(profile_name=self.aws_profile, region_name=self.aws_region)


@lru_cache
def get_settings() -> Settings:
    return Settings()
