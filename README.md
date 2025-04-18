# patchTester

## Overview
A tool to test requested Perforce integrations for conflicts. This helps avoid integration problems by identifying conflicts before they occur in production branches.

```
usage: patchTester.py [-h] -t BRANCH_TO -f BRANCH_FROM -c CLIENT [-p]
                      [-i INTEGRATIONS] [-r REQUESTS] [-d] [-v]

patchTester will evaluate pending patch requests for a branch.

optional arguments:
  -h, --help            show this help message and exit
  -t BRANCH_TO, --branch_to BRANCH_TO
                        the branch to
  -f BRANCH_FROM, --branch_from BRANCH_FROM
                        the branch from
  -c CLIENT, --client CLIENT
                        the perforce client to use
  -p, --pending         test pending not yet accepted PRQS
  -i INTEGRATIONS, --integrations INTEGRATIONS
                        comma separated list of submitted perforce changelists
  -r REQUESTS, --requests REQUESTS
                        comma separated list of PRQS
  -d, --dirty           do not cleanup client
  -v, --verbose         debug logging
```

## Features

- Pre-tests Perforce branch integrations to detect conflicts
- Identifies specific issues that may lead to integration problems
- Detailed HTML reports with conflict analysis
- Ticketing system integration for patch requests
- Handles cross-component changes
- Provides suggestions for resolving conflicts

## Installation

```bash
git clone https://github.com/yourusername/patchtester.git
cd patchtester
pip install -e .
```

### Requirements

- Python 3.6+
- P4Python
- anytree
- PyYAML
- Jinja2

## Examples

### Testing all requested changes from `dev` branch to `beta` branch

Using client `user_patchTester` that has both of these branches mapped:

```bash
patchtester -f dev -t beta -c user_patchTester
```

### Testing pending PRQ requested changes

```bash
patchtester -f dev -t beta -c user_patchTester -p
```

### Testing specific changelists

```bash
patchtester -f dev -t beta -c user_patchTester -i 123456,123457,123458
```

## How It Works

patchTester will:

1. Query the ticket system for patch requests
2. Apply the requested integrations to the specified workspace
3. Examine reported integration conflicts
4. Analyze why conflicts occur
5. Generate an HTML report with detailed suggestions

## Customization

The tool can be extended by modifying the `jirautils` and `buildInfo` modules to work with your specific ticket system and branch configuration.

## License

MIT
