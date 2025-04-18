'''
patchTester will evaluate pending patch requests for a branch.
'''
from anytree import node, search
from jinja2 import Environment, FileSystemLoader

import logging
from termutils import AskYesNo
import sys
import os
import P4

logging.getLogger(__name__).addHandler(logging.NullHandler())
_logger = logging.getLogger(os.path.basename(sys.argv[0]))


class PatchTester(object):
    """
    Tests integrations
    """
    def __init__(self, data, DEBUG):
        self.pt_data = data 
        self.p4 = data.p4
        _logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)

    def prepForIntegration(self): # NOQA - complexity accepted
        """
            prepares the client to do the integrations.
                - shelve any current changes.
                - sync to the current revison.
        """
        arch_data = None
        if hasattr(self.pt_data, 'p4_client'):
            try:
                _logger.debug('\n\nPreparing local branch/client'
                              ' for integrations\n')

                # get all opens for this client, test to see if they are
                # to destination if so ask to shelve them and revert
                pending = False
                pending_changes = self.p4.run("opened")
                if pending_changes:
                    # see if these are pending to the target branch
                    for pendch in pending_changes:
                        if pendch['depotFile'].startswith(self.pt_data.branches[0]['p4_to_prefix']):
                            pending = True
                            break

                if pending:
                    res = AskYesNo('\n\nWARNING: Open files detected at target branch in client ' +
                                   self.pt_data.p4_client + ' \n\n'
                                   'Please confirm to continue \n'
                                   '\tYes -> patchTester auto shelves'
                                   ' and reverts\n'
                                   '\tNo  -> you shelve and revert')
                    if not res:
                        _logger.debug('Pending open files detected in client!!! exiting')
                        sys.exit(1)
                    else:
                        _logger.info('Automatically shelving found open files')
                        for pending_change in pending_changes:
                            # if default change then make numbered pend change
                            if 'default' in pending_change['change']:

                                new_change = self.p4.fetch_change()
                                new_change['description'] = ("PatchTester"
                                                             " shelved \n"
                                                             "default"
                                                             " changelist")
                                # the input to this updated change
                                self.p4.input = new_change
                                new_change = self.p4.run('change', '-i')
                                # see if was made, bail if not
                                results = new_change[0].split(' ')
                                if results[0] == "Change" and \
                                   results[2] == "created":
                                    change_id = results[1]
                                    # shelve all files in this new change
                                    self.p4.run("shelve",
                                                "-c",
                                                change_id,
                                                "-f",
                                                "-a",
                                                "submitunchanged")
                                else:
                                    _logger.error('Error creating'
                                                  ' numbered change')
                                    sys.exit(1)
                            else:  # shelve all files for this changelist
                                change_id = pending_change['change']
                                self.p4.run("shelve",
                                            "-c",
                                            change_id,
                                            "-f",
                                            "-a",
                                            "submitunchanged")

                        #  Now revert all open files across all open changelists
                        _logger.info('Reverting all open files')
                        self.p4.run("revert", "//...")
            except P4.P4Exception as e:
                _logger.error('Error ' + str(e))
                sys.exit(1)

        #  give op chance to determine to sync or not
        if arch_data is None:  # no sync when archive restore
            res = AskYesNo('\n\nReady to sync branch: ' + self.pt_data.branches[0]['p4_to_prefix'] + ', Continue with sync?')
            if res:
                try:
                    # No Pending changes now, so we should sync
                    _logger.debug('p4 sync ...')
                    self.p4.run("sync", self.pt_data.branches[0]['p4_to_prefix'] + "/...")
                except P4.P4Exception as e:
                    if 'file(s) up-to-date.' in str(e):
                        _logger.debug('Tree up-to-date')
                    else:
                        _logger.error('Error ' + str(e))
                        sys.exit(1)

    def doIntegrations(self):  # NOQA - complexity accepted
        """
            Carries out the integrations and resolutions
        """
        seen_nodes = []
        for n, integrate in enumerate(self.pt_data.requested_integrates):
            # if change is number zero then it is tbd or it was not set in
            # the PRQ
            if (int(integrate) is 0):
                key = 'Pending patch or missing Requested Changelists: field'
                desc = 'No changelist available.'
                sug = ('This request depends on a request to the originating'
                       ' branch that has not been done yet or it has a PRQ '
                       ' that is missing the requested changelist. '
                       ' Try again later or fix the changelist.')
                integrate_nodes = search.findall_by_attr(self.pt_data, value=0)
                for integrate_node in integrate_nodes:
                    if integrate_node not in seen_nodes:
                        integrate_node.crosscomponent = False
                        integrate_node.errors = []    # store errors
                        integrate_node.sugs = []
                        integrate_node.errors.append({key: desc})
                        integrate_node.sugs.append({key: sug})
                        _logger.debug(key + "\n" + desc)
                        seen_nodes.append(integrate_node)
                continue

            # find this child in our tree of requested integrations
            integrate_node = search.find_by_attr(self.pt_data,
                                                 value=str(integrate))
            if not integrate_node:
                # no node for this implies that this is local integrate to higher branches
                # process special

                _logger.debug("no integrate node for this integrate searching for parent")
                integrate_node = search.find_by_attr(self.pt_data,
                                                     name="change",
                                                     value=str(integrate))

                if integrate_node:
                    _logger.debug("parent found, replacing change to integrate with original")
                    integrate_node.change = integrate_node.change_desc['change']
                    integrate = integrate_node.change_desc['change']

            if integrate_node:
                integrate_node.crosscomponent = False
                integrate_node.errors = []    # store errors
                integrate_node.warnings = []  # store warnings
                integrate_node.sugs = []      # store warnings
                _logger.info("\n\n" + "=" * 80)
                _logger.info("Change {0} for {1}"
                             .format(integrate, integrate_node.parent.req_id))
                # add details of the original change to our the node for this
                # change
                try:
                    integrate_node.change_desc = self.p4.run('describe',
                                                             int(integrate))[0]
                except P4.P4Exception as e:
                    key = 'p4 describe integrate error'
                    desc = str(e)
                    integrate_node.errors.append({key: desc})
                    _logger.debug(key + "\n" + desc)
                    continue

                # create a changelist for the integration
                new_change = self.p4.fetch_change()
                new_change['description'] = ("patchTester: test integrate"
                                             " for {} original desc: {}".
                                             format(str(integrate),
                                                    integrate_node.
                                                    change_desc['desc']))
                self.p4.input = new_change
                new_change = self.p4.run('change', '-i')

                # see if was made, go to next if not
                results = new_change[0].split(' ')
                if not results[0] == "Change" and not results[2] == "created":
                    key = 'create new change error'
                    desc = str(new_change)
                    integrate_node.errors.append({key: desc})
                    _logger.debug(key + "\n" + desc)
                    continue

                # The new changelist number
                integrate_node.change = results[1]
                self.pt_data.created_changelists.append(integrate_node.change)

                _logger.info("Integrating change {} as local change {}".
                             format(integrate, integrate_node.change))
                # cook new integration command
                integrate_cmd = ['integ', '-q', '-c', integrate_node.change, '-f',
                                 self.pt_data.p4_from_prefix + '/...@' +
                                 str(integrate) + ',' + str(integrate),
                                 self.pt_data.branches[0]['p4_to_prefix'] + '/...']
                _logger.debug(" ".join(integrate_cmd))

                # do the integration
                try:
                    warn = self.p4.run(integrate_cmd)
                    if warn:
                        # data was returned!
                        # meaning it had something to warn about
                        key = 'p4 integration warning'
                        desc = str(warn)
                        integrate_node.warnings.append({key: desc})
                        _logger.info(key + "\n" + desc)
                except P4.P4Exception as e:
                    key = 'p4 integrate error'
                    desc = str(e)
                    sug = self.suggestFix(desc, integrate_node)
                    integrate_node.errors.append({key: desc})
                    _logger.info(key + "\n" + desc)
                    integrate_node.sugs.append({key: sug})
                    _logger.debug("\n" + sug)
                    continue

                pending_chg = self.p4.run('describe', integrate_node.change)[0]
                if 'depotFile' not in list(pending_chg.keys()):
                    key = 'Failed to copy in files to new changelist'
                    desc = ('A file integration failed. Multiple requests '
                            'contained different revisions of the same file.')
                    sug = ('This warning indicates that the same file was '
                           'requested in multiple changelists. Because '
                           'PatchTester does not submit the files like '
                           'p4 patch does, it can not integrate multiple '
                           'revisions of the same file. Therefore, it '
                           'only integrates the first one. This means '
                           'that PatchTester is not really testing all '
                           'of the requested changes to that file.')
                    integrate_node.warnings.append({key: desc})
                    _logger.debug(key + "\n" + desc)
                    integrate_node.sugs.append({key: sug})
                    continue

                reslt_failed = False

                for idx, file in enumerate(pending_chg['depotFile']):
                    # if its file add (rev 1) and branching skip resolve
                    if (int(pending_chg['rev'][idx]) == 1 and
                            'branch' in str(pending_chg['action'][idx])):
                        _logger.debug("File branch rev 1, skipping " + file)
                        continue
                    try:
                        _logger.info("\n" + str(file))
                        verify_cmd = ['verify', '-q', '-s', file]
                        _logger.debug(" ".join(verify_cmd))
                        verify_result = self.p4.run(verify_cmd)
                        _logger.debug("verify_result (empty good)" + str(verify_result))

                        sync_cmd = ['sync', '-q', file]
                        _logger.debug(" ".join(sync_cmd))
                        sync_result = self.p4.run(sync_cmd)
                        _logger.debug("sync_result (empty good)" + str(sync_result))
                    except P4.P4Exception as e:
                        _logger.info("verify/sync error")
                        _logger.info(str(e))

                    try:
                        resolve_cmd = ['resolve', '-am', '-o', file]
                        _logger.debug(" ".join(resolve_cmd))
                        integrate_node.res_result = None
                        integrate_node.res_result = self.p4.run(resolve_cmd)
                    except P4.P4Exception as e:
                        if 'no file(s) to resolve.' not in str(e):
                            key = 'p4 resolve error'
                            desc = str(e)
                            integrate_node.errors.append({key: desc})
                            _logger.info("error resolving files")
                            _logger.info(key + "\n" + desc)

                    if integrate_node.res_result:
                        result_string = ""
                        for reslt in integrate_node.res_result:
                            if type(reslt) is dict:
                                if 'contentResolveType' in reslt:
                                    result_string += "contentResolveType:" + reslt['contentResolveType']
                                if 'baseRev' in reslt:
                                    result_string += "\nbaseRev:" + reslt['baseRev']
                                if 'how' in reslt:
                                    result_string += "\nhow:" + reslt['how']
                            if type(reslt) is str:
                                result_string += "\n" + reslt
                                _logger.info(reslt)
                                if 'resolve skipped.' in reslt:
                                    # no resolution
                                    break
                                elif 'Diff chunks:' in reslt:
                                    if ' 0 conflicting' not in reslt:
                                        con = reslt.split('+')[-1] \
                                                   .replace('conflicting',
                                                            'conflicts')
                                        key = 'Resolution Conflict'
                                        error = (con + ' reported for file ' +
                                                 file + "\n\n")
                                        sug = self.suggestFix('resolutionConf',
                                                              integrate_node,
                                                              file, idx)
                                        integrate_node.errors \
                                                      .append({key: error})
                                        integrate_node.sugs.append({key: sug})
                                        _logger.debug(error)
                                        reslt_failed = True
                                        break

                        _logger.debug(result_string)
                    else:
                        key = 'Error resolving ' + file
                        desc = 'Failed to resolve'
                        integrate_node.errors.append({key: desc})
                        _logger.debug(key + "\n" + desc)

                if not reslt_failed:
                    compare_to = None
                    for file in integrate_node.change_desc['depotFile']:
                        component = file.replace(self.pt_data.p4_from_prefix + '/', '').split('/')[0]
                        _logger.debug('component compared ' + component)

                        # skip the following "components"
                        if 'testSpecs' in component:
                            continue
                        elif 'SCons' in component:
                            continue
                        elif 'buildMap' in component:
                            continue

                        if not compare_to:
                            compare_to = component
                            continue
                        if compare_to != component:
                            _logger.debug('components do not match')
                            # found cross component, raise flag
                            integrate_node.crosscomponent = True
                            key = 'Cross Component Checkin'
                            error = ("Succcesfully integrated and resolved but \n" +
                                     "this changelist contains files from multiple components.")
                            sug = ("This is a warning. \n" +
                                   "These are the files in this changelist\n" +
                                   str("\n".join(integrate_node.change_desc['depotFile'])))
                            integrate_node.errors.append({key: error})
                            integrate_node.sugs.append({key: sug})
                            break

                # update self.pt_data.requested_integrates with new pending change id
                # in case we wish to integrate this change to higher branches.
                self.pt_data.requested_integrates[n] = integrate_node.change

    def suggestFix(self, error, node, file=None, idx=0): # NOQA - complexity accepted
        '''
            giant switch statement for gathering of known conditions

            @param error: the string used for look up
            @param node: the node with the change having issues.
        '''
        sug = '.' * 120 + '\n'
        if 'Warnings during command execution( "p4 integ -q -c' in error:
            if '- no such file' in error:
                if node.change_desc['status'] == 'pending':
                    sug += ('<b>Change is pending</b>\n\n'
                            'Requested change is currently pending.'
                            ' Please copy locally or submit it')
                    return sug
                if 'path' in list(node.change_desc.keys()):
                    sug += ('<b>Verify the branch of the requested'
                            ' change</b>\n\nRequested change is'
                            ' currently at : ' + node.change_desc['path'] +
                            '\nWe need it to be in this branch: ' +
                            self.pt_data.p4_from_prefix + '\n')
                    return sug
        elif 'resolutionConf' in error:  # resolution conflict
            # get the revision number we have for this file
            try:
                have = self.p4.run('have', file)[0]['haveRev']
            except P4.P4Exception as e:
                _logger.debug("failed to be able to divine missing changes")
                sug = "Please have a look at this change"
                sug += str(e)
                return sug

            rev = have

            # and the revison # we want from this file
            want = node.change_desc['rev'][idx]

            # get the basefile used in resolution
            base_file = node.res_result[0]['baseFile']

            # get the filelog of the file we have at the rev we have
            cmd = ['filelog', '-h', '-m2', file + '#' + have + ',#' + have]
            have_hist = self.p4.run(cmd)
            edits = []
            minusrev = 0
            if have_hist:
                new_hist = have_hist
                if 'file' not in list(have_hist[0].keys()):
                    # have revision does not have ancestor from other branch
                    # meaning that have revision was edit to local file
                    # loop back until we find the base we branched from
                    while True:
                        change_edit = new_hist[0]['change'][0]
                        # gather intervening local changes
                        if change_edit not in edits:
                            edits.append(change_edit)

                        newhave = int(have) - minusrev

                        cmd = ['filelog', '-h', '-m2', file + '#' +
                               str(newhave) + ',#' + str(newhave)]
                        _logger.debug("looking for new have " + " ".join(cmd))
                        new_hist = self.p4.run(cmd)
                        if 'file' in list(new_hist[0].keys()):
                            break

                        minusrev += 1
                        if minusrev > int(have):
                            _logger.debug("failed to be able to divine"
                                          " missing changes")
                            sug = "Please have a look at this change"
                            return sug
            else:
                sug = 'error please look here'
                return sug

            for idy, revision in enumerate(new_hist[0]['file'][0]):
                if revision == base_file:
                    break

            # get position in the have history data
            # for determining the file genesis
            # https://www.perforce.com/perforce/r14.2/manuals/cmdref/p4_integrated.html
            how = new_hist[0]['how'][0][idy]

            action = new_hist[0]['action'][0]
            genesis = ''
            if how == 'copy from':
                genesis = ("<b>Aquired via:</b> " + action + " in change " +
                           new_hist[0]['change'][0] + " ")
                genesis += (" as a " + how + " " + base_file + '#' + want +
                            ' accepting theirs\n')
            elif how == 'merge from ':
                genesis = ("<b>Aquired via:</b> " + action + " in change " +
                           new_hist[0]['change'][0] + " ")
                genesis += (how + " " + base_file + '#' + want +
                            ' accepting merge\n')
            elif how == 'branch from':
                if minusrev != 0:
                    # there been intervinig changes to target in branch
                    rev = new_hist[0]['erev'][0][idy].replace('#', '')
                    genesis += ("<b>Branched from " +
                                self.pt_data.p4_from_prefix.split('/')[-1] +
                                " at revision:</b> " + str(rev) +
                                " in change " + new_hist[0]['change'][0])

                    genesis += ('\n<b>Edits in ' + self.pt_data.branches[0]['name'] +
                                " since branching:</b> " + str(minusrev))
                    genesis += ("<ul style=\"margin-top:-30px"
                                ";margin-bottom:-60px\">")
                    for edit in edits:
                        change_desc = self.p4.run('describe', int(edit))[0]
                        description = change_desc['desc'].splitlines(True)
                        genesis += ("<li>Change: " + str(edit) +
                                    " \nDescription:\n" +
                                    " ".join(description[0:4]) + "</li>")
                    genesis += "</ul>"
            else:
                genesis = "Unknown Genesis for " + file + "\n\n" + how
                genesis += ("see see https://www.perforce.com/perforce"
                            "/r14.2/manuals/cmdref/p4_integrated.html")
                genesis += "\n and add cases to patchTester around line 618"

            sug += ("<b>File with conflict:</b> " + file +
                    "\n<b>Requested " +
                    self.pt_data.p4_from_prefix.split('/')[-1] +
                    " revision:</b> " + want + "\n<b>Current " +
                    self.pt_data.branches[0]['name'] + " revision:</b> " + have)

            sug += "\n" + genesis + '\n'

            if int(rev) <= int(want):
                # good! we want to move forward or we have what we want
                distance = int(want) - int(rev)
                if (distance == 1 or distance == 0):
                    # e.g. want 3 and have 2, or want 3 and have 3
                    sug += ('<b>No missing intervening changes</b><br/>'
                            'There does not appear that there are '
                            'missing intervening revisions to properly'
                            ' resolve this file. Perhaps the following diff'
                            ' command can help:')
                    sug += ('\"p4 diff2 ' + node.res_result[0]['clientFile'] +
                            ' ' + base_file + '#' + want + '\"\n\n')
                else:
                    have_plus = int(rev) + 1
                    # filelog of the file we want from the rev we have +1
                    # to the rev we want
                    cmd = ['filelog', base_file + '#' + str(have_plus) +
                           ',#' + want]
                    try:
                        want_hist = self.p4.run(cmd)
                    except P4.P4Exception as e:
                        _logger.debug("failed to be able to divine missing changes")
                        sug = "Please have a look at this change"
                        sug += str(e)
                        return sug
                    revs = ''
                    counter = 0
                    for rev, user, change in zip(want_hist[0]['rev'],
                                                 want_hist[0]['user'],
                                                 want_hist[0]['change']):
                        counter += 1
                        if change in genesis:
                            break  # catch lower bound on missing change

                        rev_str = (" revision " + str(rev) +
                                   " change: " + str(change) +
                                   " user: " + str(user))
                        revs += rev_str + "\n"

                    sug += ('<b>These are ' + str(counter) +
                            ' missing intervening changes that might help'
                            ' in resolving this conflict:</b> \n')
                    sug += revs

            if int(rev) > int(want):
                sug += ('<b>We already have revision ' + want +
                        ' in target branch</b>')
            sug += ("\n\n")
        return sug

    def generateReport(self):
        """
            walks done integrations formating result data for report
        """

        # console report and details for jinja template gathering
        requests = []
        for request in self.pt_data.children:
            req = dict(req_id=request.req_id, changes=[])
            for integrate in request.children:
                if not integrate.errors and not integrate.warnings:
                    chg = dict(orig_change=integrate.req_change,
                               result='SUCCESS',
                               sugs=None,
                               details='This change was successfully'
                                       ' integrated')
                    req['changes'].append(chg)
                    continue

                if integrate.errors:
                    errors = ''
                    sugs = ''

                    for error, sug in zip(integrate.errors, integrate.sugs):
                        for key, value in list(error.items()):
                            errors += str(key) + ": " + str(value) + "\n"
                        for key, value in list(sug.items()):
                            sugs += str(key) + ": " + str(value) + "\n"
                    if integrate.crosscomponent:
                        chg = dict(orig_change=integrate.req_change,
                                   result='WARNING',
                                   sugs=sugs.replace("\n", "<br/>"),
                                   details=errors.replace("\n", "<br/>"))
                    else:
                        chg = dict(orig_change=integrate.req_change,
                                   result='FAILED',
                                   sugs=sugs.replace("\n", "<br/>"),
                                   details=errors.replace("\n", "<br/>"))

                    req['changes'].append(chg)
                    continue

                if integrate.warnings:
                    warnings = ''
                    sugs = ''

                    for warn, sug in zip(integrate.warnings, integrate.sugs):
                        for key, value in list(warn.items()):
                            warnings += str(key) + ": " + str(value) + "\n"
                        for key, value in list(sug.items()):
                            sugs += str(key) + ": " + str(value) + "\n" 

                    chg = dict(orig_change=integrate.req_change,
                               result='FAILED',
                               sugs=sugs.replace("\n", "<br/>"),
                               details=warnings.replace("\n", "<br/>"))
                    req['changes'].append(chg)
                    continue
            requests.append(req)

        # jinja html template
        script_dir = os.path.join(os.path.dirname(__file__), 'data')
        env = Environment(loader=FileSystemLoader(searchpath=script_dir))
        template = env.get_template('email_notify.tmpl')

        subject = ("<b>from " + self.pt_data.p4_from_prefix + " to " +
                   self.pt_data.branches[0]['p4_to_prefix'] + "</b>")
        report = template.render(title='patchTester Report',
                                 subject=subject,
                                 results=requests)
        return report
        
    def cleanup(self, dirty=True):
        """
            cleans up client from made integrations unless dirty specified
        """
        if not dirty:
            _logger.info('\nCleaning made files')
            res = AskYesNo('\n\nWARNING: Deleting open files in client ' +
                           self.pt_data.p4_client + ' \n\n'
                           'Please confirm to continue \n'
                           '\tYes -> patchtester cleans up\n'
                           '\tNo  -> you cleanup')

            if not res:
                _logger.info('Not cleaning up.')
                sys.exit(1)
            else:
                try:
                    result = self.p4.run("revert", "//...")
                    _logger.debug(str(result))
                except P4.P4Exception as e:
                    if 'file(s) not opened' in str(e):
                        _logger.debug('Tree up-to-date')
                    else:
                        _logger.error('Error ' + str(e))
                        sys.exit(1)

                _logger.info('Deleting changes')
                for change in self.pt_data.created_changelists:
                    delete_result = self.p4.run('change', '-d', change)
                    _logger.debug(delete_result)
