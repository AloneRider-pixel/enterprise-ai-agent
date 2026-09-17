from dataclasses import dataclass

import httpx

from forgeai.config import Settings


class GitHubClientError(RuntimeError):
    """Raised when GitHub cannot provide a valid PR snapshot."""


@dataclass(frozen=True)
class PullRequestSnapshot:
    repository: str
    number: int
    title: str
    body: str
    additions: int
    deletions: int
    changed_files: int
    filenames: list[str]


class GitHubClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = client

    async def get_pull_request(self, repository: str, number: int) -> PullRequestSnapshot:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"

        owned_client = self._client is None
        client = self._client or httpx.AsyncClient(
            base_url=self.settings.github_api_base,
            timeout=self.settings.request_timeout_seconds,
            headers=headers,
        )
        try:
            pr_response = await client.get(f"/repos/{repository}/pulls/{number}")
            if pr_response.status_code >= 400:
                raise GitHubClientError(
                    f"GitHub PR request failed: {pr_response.status_code}"
                )
            pr = pr_response.json()

            files_response = await client.get(f"/repos/{repository}/pulls/{number}/files")
            if files_response.status_code >= 400:
                raise GitHubClientError(
                    f"GitHub files request failed: {files_response.status_code}"
                )

            filenames = [
                item.get("filename", "")
                for item in files_response.json()
                if item.get("filename")
            ]

            return PullRequestSnapshot(
                repository=repository,
                number=number,
                title=pr.get("title", ""),
                body=pr.get("body") or "",
                additions=int(pr.get("additions", 0)),
                deletions=int(pr.get("deletions", 0)),
                changed_files=int(pr.get("changed_files", len(filenames))),
                filenames=filenames,
            )
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise GitHubClientError("Invalid GitHub response") from exc
        finally:
            if owned_client:
                await client.aclose()
