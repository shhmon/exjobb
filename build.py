import click
import subprocess
from tqdm import tqdm
from extract import Extractor
from github_fetch import fetch_responses, parse_pull_requests, fetch_data
from utils import dump, quiet_flag, cloned, keyper, single, load
from os import getcwd

"""
Dataset building script. PRs from provided repo will be fetched in the following format:
Out: [{pr_keys, commits:[cm_keys], docs (optional):[(filepath, content)]}]
"""

# Values to extract from PR json response
pr_keys = (
	'number',
	'title',
	'labels',
	'state',
	'pull_request',
	'body'
)

# Values to extract from commit json response
cm_keys = (
	'sha',
	'html_url',
	'commit',
	'files',
	'stats'
)

# Get url for repo cloning from user/repo
cl_url = lambda user, repo: f'https://github.com/{user}/{repo}.git'
# Get url for PR fetching from user/repo
pr_url = lambda user, repo: f'https://api.github.com/repos/{user}/{repo}/issues?per_page=100&state=closed'
# Get url for commits belonging to a PR
cs_url = lambda user, repo, pnr: f'https://api.github.com/repos/{user}/{repo}/pulls/{pnr}/commits'
# Get url for commit content of certain commit
cm_url = lambda user, repo, sha: f'https://api.github.com/repos/{user}/{repo}/commits/{sha}'

# Checkout every PR and extend with doc data
def extract_docs(cwd, data):
	dwd = f'{cwd}/docs'

	def checkout_extract(pr):
		pr_num = pr['number']

		if 'merged_at' in pr['pull_request']:
			subprocess.run(f'git pr {pr_num} {quiet_flag}', cwd=cwd, shell=True)
			mdpaths, mdcontents = Extractor('md').extract(dwd)
			rspaths, rscontents = Extractor('rst').extract(dwd)

			paths = mdpaths + rspaths
			contents = mdcontents + rscontents

			# Make paths relative to repo root
			paths = [*map(lambda p: p.replace(f'{getcwd()}/', ''), paths)]

			return [*zip(paths, contents)]
		else:
			raise ValueError('PR not merged')

	ret = []

	# Remove from dataset if ValueError (doc folder does not exist or pr not merged)
	for pr in data:
		try:
			ret.append({'docs': checkout_extract(pr), **pr})
		except ValueError:
			pass
	
	return ret

def get_pull_requests(token, u, r):
	responses = fetch_responses(token, pr_url(u, r))
	prs = parse_pull_requests(responses)

	# Filter keys
	return [*map(keyper(pr_keys), prs)]


def get_commits(pnr, token, u, r):
	# Get extended commit info for a sha
	get_commit = lambda sha: single(fetch_data)(
		token, cm_url(u, r, sha),
	)

	# Get from /pr url, extract sha and fetch full
	pr_cms, rem	= fetch_data(token, cs_url(u, r, pnr))
	shas = [*map(lambda c: c['sha'], pr_cms)]

	if int(rem) < len(shas):
		raise ConnectionError('Out of API calls')
	else:
		commits = [*map(get_commit, shas)]
	
	return [*map(keyper(cm_keys), commits)]

@click.command()
@click.option('--token', '-t', help='GitHub API user authentication token')
@click.option('--repo', '-r', help='Target user and repo: e.g backtick-se/cowait')
@click.option('--out', '-o', help='Outfile path', default=None)
@click.option('--docs', '-d', is_flag=True, default=False)
@click.option('--resume', '-c', is_flag=True, default=False)
def run(token: str, repo: str, out: str, docs: bool, resume: bool):
	"""
    Ex. usage:
    python build.py -t $token -r backtick-se/cowait -o dataset.pickle
    """

	# User, repo
	u, r = repo.split('/')

	out = out if out else f'data/prd_{u}_{r}.pickle'

	if not resume:
		# Get the PR data
		click.echo('Fetching PR data...')
		pr_data = get_pull_requests(token, u, r)

		if docs:
			# Clone, checkout and save doc state for every PR
			click.echo('Extracting doc states...')
			data = cloned(cl_url(u, r))(extract_docs)(tqdm(pr_data))
	
		click.echo('Fetching commit data...')
	else:
		# Load from "out" file location
		data = load(out)
		click.echo('Resuming commit data fetch...')
	
	# Fetch, filter and add commit data to PRs
	try:
		for pr in tqdm(*filter(lambda p: 'commits' not in p, data)):
			pr['commits'] = get_commits(pr['number'], token, u, r)
	except ConnectionError as e:
		fetched = len([*filter(lambda pr: 'commits' in pr, data)])
		click.echo(f'Ran out of API calls, {fetched}/{len(data)} prs complete')

	click.echo(f'Done! Saving to {out}')

	dump(data, out)

if __name__ == '__main__':
	run()
