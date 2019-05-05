import argparse
import logging
import platform
import os
import os.path
import pathlib
import functools
import subprocess
import datetime
import sys
import re
import tempfile
import shutil

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

datestring = "%Y_%m_%d_%H_%M_%S"

#set PATH=%PATH%;C:\Users\peter.guenther\Documents\workspaces\HardLink\Hardlink\bin\Release
#python3 backup.py --sources C:\Users\peter.guenther\Documents\thesis_new --destination h:\backup\laptop --dry-run

@functools.total_ordering
class Backup:
    def __init__(self,path,date):
        self.path = path
        self.date = date

    def __str__(self):
        return f"Backup from {self.date} @ {self.path}"

    def __lt__(self,other):
        return self.date <= other.date

    def __eq__(self,other):
        return self.date == other.date and self.path == other.path


    @classmethod
    def __guess_time__(cls,path):
        fbase = os.path.basename(path)
        try:
            astime =  datetime.datetime.strptime(fbase,datestring)
            return astime
        except ValueError:
            return None

    @classmethod
    def is_backup(cls,path):
        return cls.__guess_time__(path) is not None

    @classmethod
    def from_path(cls,path):
        date = cls.__guess_time__(path)
        return cls(path,date)


def unify_path(path,drive_prefix='\cygdrive'):
    drive,subpath = os.path.splitdrive(path)
    if drive == "":
        logger.debug(f"Path {path} does not contain drive.")
        return path
    else: 
        match = re.match('\s*(?P<drive>\w):',drive)
        if match:
            drive = match.group('drive')
            logger.debug(f"Identified drive {drive}")
            replacement  = os.path.join(drive_prefix, drive + subpath)

            logger.warning(f"Replace path {path} with {replacement}")
            return replacement
        else:
            logger.error(f"Not a valid drive: {drive}")
            return path


def execute_system_command(cmd):
    string = ""
    for e in cmd:
        string += e + " " 

    logger.info(f"Execute {string}")


    #completed_process  = subprocess.run(cmd,check=False,shell=False,capture_output=True)
    completed_process  = subprocess.run(cmd,check=False,shell=False)

    try:
        completed_process.check_returncode()
    except subprocess.CalledProcessError as e:
        logger.error(f"Error occured during execution of {e.cmd}")
        logger.error(f"Returncode: {e.returncode}")
        logger.error(f"Output: {e.output}")
        logger.error(f"stdout: {e.stdout}")
        logger.error(f"stderr: {e.stderr}")

    return completed_process
    

def compile_rsync_command(src,dest,target_fst,dry_run=True,logfile=None,link_dest=None,thorough_check=False):
    cmd=["rsync"]
    rsync_filters = []
    #['--exclude=lost+found', '--exclude=.cache/']

    rsync_options = ["--delete","--ignore-existing","--hard-links","--sparse"]

    if target_fst == "NTFS":
        rsync_options += ["--no-perms", "--no-owner", "--no-group"]
        #emulate --archive, but without --times --perms --ownder --group
        rsync_options += ['-rlD']
    else:
        rsync_options += ["--archive"]


    for o in rsync_options+rsync_filters:
        cmd+= [o] 
        
    if logfile is not None:
        cmd+= ["--log-file=" + logfile]

    if dry_run:
        cmd += ["--dry-run"]

    if link_dest is not None:
        cmd+= ["--link-dest=" + link_dest ]

    if thorough_check:
        cmd += ["--checksum"]

    cmd+= [src_dir_normalized]

    #second positional argument of rsycn: dest
    #backup_path_unified = unify_path(backup.path)
    cmd+= [dest]
    return cmd

def compile_hardlink_command(src,dest,target_fst,dry_run=True,logfile=None,link_dest=None,thorough_check=False):
    cmd =[]

    if dry_run:
        cmd+=["echo"]

    cmd += ["HardLink"]

    cmd += [f"--source-folder",src]
    cmd += [f"--destination",dest]
    if link_dest is not None:
        cmd += [f"--link-dest",link_dest]
    cmd += [f"--logfile",logfile]

    return cmd

#compile_backup_command=compile_hardlink_command
compile_backup_command=compile_rsync_command

if __name__ == "__main__":
    errors = 0

    parser = argparse.ArgumentParser()

    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--target-fst',default='NTFS')
    parser.add_argument('--sources',nargs='*',required=True,type=str)
    parser.add_argument('--destination',nargs=1,required=True,type=str)

    args = parser.parse_args()
    source_dirs = args.sources


    

    target_fst = args.target_fst


    hostname=platform.node()

    now = datetime.datetime.now()


    destbase = args.destination[0]
    logger.debug(f"Destination backup directory {destbase}")
    
    datedir = now.strftime(datestring)

    if not os.path.isdir(destbase):
        logging.error(f"The destination directory {destbase} does not exist or is not a direcotry.")   
        sys.exit()
    
  
    destdir = os.path.join(destbase,datedir)
    logging.debug(f"Destination directory {destdir}")

    backup = Backup(destdir,now)

    existing_backups = []
    for f in os.listdir(destbase):
        fpath = os.path.join(destbase,f)
        if os.path.isdir(fpath):
            fbase = os.path.basename(fpath)
            logger.debug(f"Found directory {fbase} in backup destination.")
            if Backup.is_backup(fpath):
                existing_backups.append(Backup.from_path(fpath))

    
    existing_backups.sort()
    logging.info(f"Found {len(existing_backups)} backups.")
    for b in existing_backups:
        logger.debug(str(b))

    if existing_backups:
        last_backup= existing_backups[-1]
        logging.info(f"Last backup was {last_backup}")
        first_backup_of_month = last_backup.date.month != now.month or last_backup.date.year != now.year
    else:
        logger.info("No backups existing yet.")
        last_backup = None
        first_backup_of_month = True






        
    logfile = os.path.normpath(backup.path) + ".log"
    logger.info(f"Log to {logfile}")

    if last_backup is not None:
        link_dest = os.path.normpath(last_backup.path + '/')
        logger.info(f"Create backup at {backup} relative to {last_backup}.")
    else:
        link_dest = None
 
    #tmpdest = tempfile.mkdtemp(dir=destbase)
    tmpdest = os.path.join(destbase , 'tmpdir')
    os.mkdir(tmpdest)

    logger.info(f"Temporary backup destination {tmpdest}")

    backup_errors=0
    for src_dir in source_dirs:
        if os.path.isdir(src_dir):
            logging.info(f"Backup {src_dir}...")

            
            #we already know that src_dir is a directory, hence normpath will remove potential trailing slashes 
            
            #first positional argument of rsync: src
            src_dir_normalized = os.path.normpath(src_dir) 
            #src_dir_unified = unify_path(src_dir_normalized)

            src_head,src_tail = os.path.split(src_dir_normalized)
            if src_tail == '':
                #if there was a trailing slash in the path name
                src_head,src_tail = os.path.split(src_head)
            

            dest = tmpdest
            src = os.path.join(src_head,src_tail)
            if link_dest is None:
                link_dest_dir = None
            else:
                link_dest_dir = os.path.join(link_dest,src_tail)

            cmd=compile_backup_command(target_fst=args.target_fst,dry_run=args.dry_run,logfile=logfile,src=src,dest=dest,link_dest=link_dest_dir,thorough_check=first_backup_of_month)


            if errors>0:
                logger.info("Skip rsync because errors happened.")
            # elif args.dry_run:
            #     logger.info("Skip rsync for dry run")
            else:
                completed_process = execute_system_command(cmd)
                if completed_process.returncode != 0:
                    backup_errors+=1
                    logger.error(f"Error during execution of {cmd[0]}.")

                
        else: 
            logging.warning(f"{src_dir} is not a directory. Skip for backup.")


    if backup_errors>0:
        logger.error(f"Errors during backup. Stop backup. Manually remove temporary dir {tmpdest}")
    elif not args.dry_run:
        logger.debug(f"Move temporary directory {tmpdest} to {backup.path}")
        try:
            os.rename(tmpdest,backup.path)
        except OSError as e:
            logger.error(f"Renaming failed with {e}")
    else:
        logger.info(f"Remove temporary directory {tmpdest}")
        try:
            shutil.rmtree(tmpdest)            
        except:
            logger.error(f"Error during removal of {tmpdest}. Remove manually.")
        


