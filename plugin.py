from __future__ import annotations

from LSP.plugin import IsApplicableContext
from LSP.plugin import LspPlugin
from LSP.plugin import OnPreStartContext
from LSP.plugin import parse_uri
from LSP.plugin import Promise
from LSP.plugin import request_handler
from LSP.plugin import WorkspaceFolder
from lsp_utils import NodeManager
from lsp_utils.helpers import run_command_sync
from pathlib import Path
from sublime_lib import ResourcePath
from typing import final
from typing import TypedDict
from typing_extensions import override
import re


class RepoInfo(TypedDict):
    organizationOwned: bool


class Repo(RepoInfo):
    id: int
    owner: str
    name: str
    organizationOwned: bool
    workspaceUri: str


class ReadFileParams(TypedDict):
    path: str


@final
class LspActionsPlugin(LspPlugin):

    @classmethod
    def is_applicable_async(cls, context: IsApplicableContext) -> bool:
        file_path = context.view.file_name()
        return super().is_applicable_async(context) and (not file_path or is_github_workflow_file(Path(file_path)))

    @classmethod
    @override
    def on_pre_start_async(cls, context: OnPreStartContext) -> None:
        package_name = cls.plugin_storage_path.name
        NodeManager.on_pre_start_async(
            context,
            cls.plugin_storage_path,
            ResourcePath('Packages', package_name, 'server'),
            Path('node_modules', '@actions', 'languageserver', 'bin', 'actions-languageserver'),
            node_version_requirement='>=20',
        )
        if not context.configuration.initialization_options.get('sessionToken'):
            context.configuration.initialization_options.set('sessionToken', get_github_token())
        context.configuration.initialization_options.set('repos', get_repos_configs(context.workspace_folders))

    @request_handler('actions/readFile')
    def handle_read_file(self, params: ReadFileParams) -> Promise[str]:
        scheme, filepath = parse_uri(params['path'])
        if scheme == 'file':
            return Promise.resolve(Path(filepath).read_text(encoding='utf-8'))
        msg = f'Scheme {scheme} not supported'
        raise RuntimeError(msg)


def plugin_loaded() -> None:
    LspActionsPlugin.register()


def plugin_unloaded() -> None:
    LspActionsPlugin.unregister()


def is_github_workflow_file(path: Path) -> bool:
    fragment_parts = ('.github', 'workflows')
    fragments_len = len(fragment_parts)
    path_parts = path.parts
    return any(path_parts[i:i + fragments_len] == fragment_parts for i in range(len(path_parts) - fragments_len + 1))


def get_github_token() -> str | None:
    token, _ = run_command_sync(['gh', 'auth', 'token'])
    return token


def get_repos_configs(workspace_folders: list[WorkspaceFolder]) -> list[Repo]:
    configs: list[Repo] = []
    for index, folder in enumerate(workspace_folders):
        git_root, _ = run_command_sync(['git', 'rev-parse', '--show-toplevel'], cwd=folder.path)
        if not git_root:
            continue
        remote_url, _ = run_command_sync(['git', 'remote', 'get-url', 'origin'], cwd=git_root)
        if not remote_url:
            continue
        owner, name = parse_github_remote(remote_url)
        if not owner or not name:
            continue
        info = get_repo_info(owner, name, git_root)
        configs.append(
            {
                'id': index,
                'owner': owner,
                'name': name,
                'organizationOwned': info['organizationOwned'] if info else False,
                'workspaceUri': f'file://{git_root}',
            },
        )
    return configs


def parse_github_remote(url: str) -> tuple[str, str] | tuple[None, None]:
    # SSH format: git@github.com:owner/repo.git
    if match := re.search(r'git@github\.com:([^/]+)/([^/.]+)', url):
        return match.group(1), match.group(2).removesuffix('.git')
    # HTTPS format: https://github.com/owner/repo.git
    if match := re.search(r'github\.com/([^/]+)/([^/.]+)', url):
        return match.group(1), match.group(2).removesuffix('.git')
    return None, None


def get_repo_info(owner: str, repo: str, git_root: str) -> RepoInfo | None:
    result, _ = run_command_sync([
        'gh', 'repo', 'view', f'{owner}/{repo}',
        '--json', 'isInOrganization',
        '--template', '={{.isInOrganization}}',
    ], cwd=git_root)
    if match := re.match(r'^=(.+)$', result):
        return {
            'organizationOwned': match.group(1) == 'true',
        }
    return None
