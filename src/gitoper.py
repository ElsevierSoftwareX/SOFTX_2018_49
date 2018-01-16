import datetime
import os
import sys

from subprocess import check_output, CalledProcessError, call


class GitOperations(object):
    def __init__(self, repo, caching, errpath="giterr.log"):
        self.repo = repo
        self._gitrepo = os.path.join(repo, '.git')
        self._errfile = open(errpath, "w+", 0)
        self._cache = {}
        self._caching = caching
        self._trees = {}
        self._sizes = {}
        self.years = range(self._first_year(), self._last_year() + 1)

    def cached_command(self, list, return_exit_code=False):
        """
        Executes the specified git command and returns its result.
        Subsequent executions of the same command return the cached result
        If return_exit_code is set, then the return value is True of False
        depending on whether the command exited with 0 or not.
        """

        list = ['git', '--git-dir', self._gitrepo] + list
        command = " ".join(list)
        if command in self._cache:
            return self._cache[command]
        else:
            try:
                # print(command)
                out = check_output(list, stderr=self._errfile)
                if return_exit_code:
                    out = True
            except CalledProcessError as e:
                if return_exit_code:
                    out = False
                else:
                    message = "Error calling %s: %s" % (command, str(e))
                    sys.stderr.write(message)
                    self._errfile.write(message)
                    out = None
            if self._caching:
                self._cache[command] = out
            return out

    def fill_trees(self, commit, contents):
        if not commit in self._trees:
            self._trees[commit] = set([''])

        trees = []
        for cont in contents:
            splitted = cont.split(" ")
            path = splitted[-1].split("\t")[-1]
            if splitted[1] == "tree" and path not in self._trees[commit]:
                trees.append(path)

        self._trees[commit].update(trees)

    def _first_year(self):
        """
        Returns the year of the repo's first commit(s)
        """
        first_years = self.cached_command(['log', '--max-parents=0',
                                         '--date=format:%Y',
                                         '--pretty=%ad',
                                         'master']
                                         ).splitlines()
        return int(sorted(first_years)[0])

    def _last_year(self):
        """
        Returns the year of the repo's last commit
        """
        return int(self.cached_command(['log', '-n', '1',
                                         '--date=format:%Y',
                                         '--pretty=%ad',
                                         'master']
                                         ))

    def branches(self):
        """
        Returns branches in the form:
        <commit_hash> refs/heads/<branchname>
        """
        try:
            branchrefs = self.cached_command(['for-each-ref',
                    '--format=%(objectname) %(refname)', 'refs/heads/']
                                             ).splitlines()
            branches = [ref.strip() for ref in branchrefs]
            return branches
        except CalledProcessError as e:
            print "branches error: %s" % str(e)
            return None

    def tags(self):
        """
        Returns tags in the form:
        <commit_hash> refs/tags/<tagname>
        """
        try:
            tagrefs = self.cached_command(['for-each-ref',
                    '--format=%(objectname) %(refname)', 'refs/tags/']
                                          ).splitlines()
            tags = [ref.strip() for ref in tagrefs]
            return tags
        except CalledProcessError as e:
            print "tags error: %s" % str(e)
            return None

    def commits(self, y, m, d):
        """
        Returns a list of commit hashes for the given year, month, day
        """
        end = datetime.date(y, m, d)
        start = end - datetime.timedelta(days=1)
        commits = self.cached_command(['log',
                                       '--after',
                                       '%04d-%02d-%02d' % (start.year,
                                                           start.month,
                                                           start.day),
                                       '--before',
                                       '%04d-%02d-%02d' % (y, m, d),
                                       '--pretty=%H']).splitlines()
        commits = [commit.strip() for commit in commits]
        return commits

    def last_commit_of_branch(self, branch):
        """
        Returns the last commit of a branch.
        """
        try:
            commit = self.cached_command(['rev-list', '-n', '1', branch, '--']
                                         ).strip()
            return commit
        except CalledProcessError as e:
            print "last commit of branch error: %s" % str(e)
            return None

    def commit_of_tag(self, tag):
        """
        Returns the commit of a tag.
        """
        try:
            commit = self.cached_command(['rev-list', '-n', '1', tag, '--']
                                         ).strip()
            return commit
        except CalledProcessError as e:
            print "commit of tag error: %s" % str(e)
            return None

    def commit_log(self, commit):
        """
        Returns commit log
        """
        try:
            return check_output(
                ['git', '--git-dir', self._gitrepo, 'log', commit],
                stderr=self._errfile
            )
        except CalledProcessError as e:
            print "commit_log error: %s" % str(e)
            return None

    def commit_parents(self, commit):
        """
        Returns commit parents
        """
        return []

    def commit_descendants(self, commit):
        """
        Returns commit descendants
        """
        return []

    def commit_names(self, commit):
        """
        Returns names associated with commit
        """
        return []

    def directory_contents(self, commit, path):
        """
        Returns the contents of the directory
        specified by `path`
        """
        if path:
            path += "/"

        try:
            contents = self.cached_command(['ls-tree',
                    commit, path]).splitlines()

            self.fill_trees(commit, contents)

            contents = [c.split(" ")[-1].split("\t")[-1].split("/")[-1] for c in contents]
            return contents
        except CalledProcessError as e:
            print "directory_contents error: %s" % str(e)
            return []

    def is_dir(self, commit, path):
        if commit in self._trees:
            return path in self._trees[commit]
        try:
            object_type = self.cached_command(['cat-file', '-t',
                                               '--allow-unknown-type',
                                               "%s:%s" % (commit, path)]).strip()
            return object_type == "tree"
        except CalledProcessError as e:
            return False

    def file_contents(self, commit, path):
        return check_output(['git', '--git-dir', self._gitrepo, 'show',
                "%s:%s" % (commit, path)], stderr=self._errfile)

    def file_size(self, commit, path):
        if not commit in self._sizes:
            self._sizes[commit] = {}

        if path in self._sizes[commit]:
            return self._sizes[commit][path]

        contents = self.file_contents(commit, path)
        size = 0
        if contents:
            size = len(contents)

        self._sizes[commit][path] = size
        return size
