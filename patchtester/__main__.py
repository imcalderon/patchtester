#!/usr/bin/env python
'''
patchTester will evaluate pending patch requests for a branch.
'''

import argparse
from anytree import Node, search
from buildInfo.releaseInfo import ReleaseInfoCollection
from collections import defaultdict
from email.mime.text import MIMEText
from jirautils import patch_request
import getpass
import logging
import os
import P4
import smtplib
import sys
import yaml
from yaml.representer import Representer
yaml.add_representer(defaultdict, Representer.represent_dict)

import patchtester
_logger = logging.getLogger(os.path.basename(sys.argv[0]))

def send_report(payload, subject):
    '''
        email report to logged in user

        @param payload: The html payload string
        @param subject: The subject string
    '''
    _logger.info("\nSending Email Report")
    from_address = "{0}@example.com".format(getpass.getuser())

    msg = MIMEText(payload, 'html')
    msg["Subject"] = subject
    msg["From"] = from_address
    msg["To"] = from_address

    # You'll need to configure your own SMTP server here
    # This is a placeholder
    try:
        server = smtplib.SMTP("localhost")
        server.sendmail(from_address, from_address, msg.as_string())
        server.quit()
    except:
        _logger.warning("Could not send email. SMTP server may not be configured.")
        _logger.warning("Report output:\n" + payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument('-t', '--branch_to',
                        help='the branch to', 
                        type=lambda x: x.split(','),
                        required=True)
    parser.add_argument('-f', '--branch_from',
                        help='the branch from',
                        required=True)
    parser.add_argument('-c', '--client',
                        help='the perforce client to use',
                        required=True)
    parser.add_argument('-p', '--pending',
                        action="store_true",
                        help='test pending not yet accepted PRQS',
                        required=False)
    parser.add_argument('-i', '--integrations',
                        help='comma separated list of submitted changelists',
                        type=lambda x: x.split(','),
                        required=False)
    parser.add_argument('-r', '--requests',
                        help='comma separated list of PRQS',
                        type=lambda x: x.split(','),
                        required=False)
    parser.add_argument('-d', '--dirty',
                        action='store_true',
                        help='do not cleanup client',
                        required=False)
    parser.add_argument('-v', '--verbose',
                        action='store_true',
                        help='debug logging',
                        required=False)
    args = parser.parse_args()

    if args.verbose:
        log_format = "[%(levelname)s - %(lineno)s - %(funcName)s ] %(message)s"
        formatter = logging.Formatter(log_format)
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        _logger.addHandler(ch)
        _logger.setLevel(logging.DEBUG)
        DEBUG = 1
    else:
        log_format = "%(message)s"
        formatter = logging.Formatter(log_format)
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        _logger.addHandler(ch)
        _logger.setLevel(logging.INFO)
        DEBUG = 0


    # Tree data structure; root is base.
    _logger.debug('Building root node')
    ptData = Node('root', parent=None)

    # get the desired target branches
    ptData.branches = []
    target_name = None
    short_name = None
    for branch in args.branch_to:
        branch_info = ReleaseInfoCollection().GetReleaseByName(branch)
        if branch_info is None:
            _logger.info('branch ' + str(branch) + ' not found.')
            sys.exit(1)

        branch_obj = defaultdict(list)
        branch_obj['name'] = short_name = branch_info.version
        target_name = branch_info.release_name
        branch_obj['release_name'] = target_name
        branch_obj['p4_to_prefix'] = branch_info.stream_prefix
        ptData.branches.append(branch_obj)

        from_branch = ReleaseInfoCollection().GetReleaseByName(args.branch_from)
        if ( args.branch_from == 'dev'):
            from_branch.stream_prefix = "//depot/streams/dev"
        elif from_branch is None:
            _logger.info('branch ' + str(args.branch_from) + ' not found.')
            sys.exit(1)

        ptData.p4_from_prefix = from_branch.stream_prefix

    # list of all changelists created for clean up at end
    ptData.created_changelists = []

    # the client to use
    valid = False
    if args.client:  
        try:
            _logger.debug('looking up client ' + args.client)
            p4 = P4.P4(client=args.client)
            p4.connect()
            valid = p4.run("clients", "-e", args.client)
        except P4.P4Exception as e:
            _logger.error('Error ' + str(e))
            sys.exit(1)
    else:
        try:
            _logger.info('no client specified; creating ... WIP')
            valid = False
        except P4.P4Exception as e:
            _logger.error('Error ' + str(e))
            sys.exit(1)

    if not valid:
        _logger.error('Error client \"' + args.client +'\" was not found')
        sys.exit(1)

    ptData.p4 = p4
    ptData.p4_client = args.client

    # get the requested integrations
    ptData.requested_integrates = []
    dep_data = []
    fixup_req = False
    if args.integrations: # case 1: passed in list of changes
        # since no PRQ id; we label this as a "local"
        local = Node('local', req_id='local', parent=ptData)
        for change in args.integrations:  
            ptData.requested_integrates.append(change)
            Node(change, req_change=change, parent=local)

    elif args.requests: # case 2: passed in list of PRQS
        for request in args.requests:
            try:
                result = patch_request.getVersionPatch(request)
            except patch_request.PatchRequestError as e:
                _logger.error('\n\nError with '+ request + ' skipping it') 
                continue
            dep_data.append(result)
        fixup_req = True
    elif args.pending: # case 3: pending PRQs
        dep_data = patch_request.getPendingVersionPatches(target_name)
        fixup_req = True
    else: # case 4: normal run. requested PRQS that have been accepted
        dep_data = patch_request.getAcceptedVersionPatches(target_name)
        fixup_req = True

    if not dep_data and fixup_req:
        _logger.info('No patch requests found for branch {}'.format(
                      short_name))
        sys.exit(1)

    if fixup_req:
        requests = defaultdict(list)
        for request in dep_data:
            if request.changes: # only add those that have existing changes
                for change in request.changes:
                    requests[str(request.id)].append(change)
                    ptData.requested_integrates.append(change)
            else:
                # request has no changes, it depends on patch
                # in originating branch that has not been done yet.
                requests[str(request.id)].append(0)
                ptData.requested_integrates.append('0')

        #  add all requests and changes (uniques) to the tree
        for req in requests:
            # The requests go on the 2nd level of tree
            new_node = Node(req, req_id=req, parent=ptData)
            for change in requests[str(req)]:
                # Requested integrates go on 3rd level
                Node(change, req_change=change, parent=new_node)

    ptData.requested_integrates.sort() # in order from lowest to highest

    # now with data init the class
    pt = patchtester.PatchTester(ptData, DEBUG)

    report = ""
    for branch in pt.pt_data.branches:
        pt.prepForIntegration()
        pt.doIntegrations()   
        report += pt.generateReport()
        pt.pt_data.branches = pt.pt_data.branches[1:]
        #break if no new branches 
        if pt.pt_data.branches == []:
            break

    pt.cleanup(args.dirty)
    send_report(report, 'patchTester Report')


if __name__ == '__main__':
    main()
