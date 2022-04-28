import click
from utils import load, dump, cloned
from github_fetch import fetch_data
import requests
import re
from tqdm import tqdm

diff_url = lambda user, repo, pnr: f'https://github.com/{user}/{repo}/pull/{pnr}.diff'

pattern = re.compile('a\/.*\.([a-z]*)$')

include = (
	# C, C++
	'c', 'cpp', 'cc', 'h', 'o',
	# C#
	'cs',
	# Python
	'py',
	# Java,
	'java',
	# Js/Ts
	'js', 'ts',
	# PHP
	'phtml', 'php', 'php3', 'php4', 'php5', 'phps', 'phpt',
	# Ruby,
	'rb',
	# Go
	'go',
	# Web
	'html', 'htm', 'xml', 'css', 'scss', 'sass', 'xlf', 'less',
	# General files
	'json', 'yaml', 'md', 'rst', 'txt', 'yml', 'sh', 'sql'
)

@click.command()
@click.option('--file', '-f', help='Dataset file')
def main(file):
	data = load(file)

	extended = {}

	for (id, num), value in tqdm(data.items()):
		u, r = id.split('/')
		url = diff_url(u, r, num)
		res = requests.get(url)
		
		if res.status_code == 200:
			diffs = []

			# Each file is separated by diff --git
			split = res.text.split('diff --git ')[1:]

			# For every file
			for entry in split:

				file = entry.split('\n')[0].split(' ')[0]

				# Throws error if no match (no extension)
				try:
					filetype = pattern.match(file).group(1)
				except:
					filetype = ''

				# If filetype in include, append diff
				if filetype in include:
					diffs.append(entry)
			
			# Insert this pr with diffs to extended dataset
			extended[(id, num)] = {**value, 'diffs': diffs}

		else:
			print(f'Request failed (status {res.status_code})')
	
	dump(extended, 'out.pickle')

if __name__ == '__main__':
	main()