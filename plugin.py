from __future__ import annotations

from LSP.plugin import LspPlugin
from LSP.plugin import OnPreStartContext
from LSP.plugin import parse_uri
from LSP.plugin import Promise
from LSP.plugin import request_handler
from LSP.plugin import Session
from LSP.plugin import WorkspaceFolder
from lsp_utils import NodeManager
from lsp_utils.helpers import run_command_sync
from pathlib import Path
from sublime_lib import ResourcePath
from typing import final
from typing import TYPE_CHECKING
from typing import TypedDict
from typing_extensions import override
import re
import shutil

if TYPE_CHECKING:
    from weakref import ref


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
    is_gh_present = False

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
        cls.is_gh_present = bool(shutil.which('gh'))
        if cls.is_gh_present and not context.configuration.initialization_options.get('sessionToken'):
            context.configuration.initialization_options.set('sessionToken', get_github_token())
        context.configuration.initialization_options.set('repos', get_repos_configs(context.workspace_folders,
                                                                                    is_gh_present=cls.is_gh_present))

    def __init__(self, weaksession: ref[Session]) -> None:
        super().__init__(weaksession)
        if not self.is_gh_present and (session := weaksession()):
            session.set_config_status_async('no gh')

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


def get_github_token() -> str | None:
    token, _ = run_command_sync(['gh', 'auth', 'token'])
    return token


def get_repos_configs(workspace_folders: list[WorkspaceFolder], *, is_gh_present: bool) -> list[Repo]:
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
        info = is_gh_present and get_repo_info(owner, name, git_root)
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
