#!/bin/bash

f () {
    errcode=$? # save the exit code as the first thing done in the trap function
    echo "error $errorcode"
    echo "the command executing at the time of the error was"
    echo "$BASH_COMMAND"
    echo "on line ${BASH_LINENO[0]}"
    # do some error handling, cleanup, logging, notification
    # $BASH_COMMAND contains the command that was being executed at the time of the trap
    # ${BASH_LINENO[0]} contains the line number in the script of that command
    # exit the script or return to try again, etc.
    exit $errcode  # or use some other value or do return instead
}
trap f ERR

MNT_DIR=/mnt/backup
BACKUP_DIR=${MNT_DIR}/linux_lab
DPKG_BACKUP_DIR=/root/dpkg
DATESTRING="+%F_%H-%M-%S"
#SRC="/etc /home  /var /root /mnt/daten"
SRC="/etc /home  /var /root"
#SRC="/etc"

#RSYNC_OPTIONS="--archive  --relative --delete --ignore-existing "
RSYNC_OPTIONS="--archive  --delete --ignore-existing "

#use for NTFS to avoid copying for ownership simulation
RSYNC_OPTIONS=${RSYNC_OPTIONS}" --no-perms --no-owner --no-group"



#FILTER="--filter + /home/peter + /etc + /opt + /var + /root - *"
#FILTER='--include=/etc --include=/home  --include=/var --include=/root --include=/mnt/daten/* --exclude=/*  lost+found'
FILTER='--exclude=lost+found --exclude=.cache/'


if mount | grep ${MNT_DIR}; then
    echo "${MNT_DIR} already mounted"
    DO_UMOUNT=0
else
    echo "Mount $BACKUP_DEVICE..."
    mount $MNT_DIR
    if test $? -ne 0; then
	echo "Failed ..."
	exit 1
    fi
    DO_UMOUNT=1
fi

echo "clean apt cache..."
aptitude clean 
if test $? -ne 0; then
    echo "Failed!"
    exit 1
fi

echo "write selected packages ..."
dpkg --get-selections > $DPKG_BACKUP_DIR/dpkg.list
if test $? -ne 0; then
    echo "Failed!"
    exit 1
fi
cp -R /etc/apt/sources.list* $DPKG_BACKUP_DIR/
if test $? -ne 0; then
    echo "Failed!"
    exit 1
fi
apt-key exportall > $DPKG_BACKUP_DIR/Repo.keys
if test $? -ne 0; then
    echo "Failed!"
    exit 1
fi

DATE=`date $DATESTRING`
DEST=$BACKUP_DIR/$DATE
LAST=`find $BACKUP_DIR -maxdepth 1 -mindepth 1 -type d  | sort | tail -1`

echo "Last backup was $LAST"

#get current month prefixed with year
MONTH=`echo $DATE | egrep -o '^[0-9]{4}\-[0-9]{2}'`

#get month prefixed with year of last backup
LAST_MONTH=`echo $LAST | egrep -o '[0-9]{4}\-[0-9]{2}'`

echo "We are in month $MONTH. Last backup was in $LAST_MONTH."

if [ "$MONTH" == "$LAST_MONTH" ]; then
    echo "Not first backup of month. Do fast comparision"
else
    echo "First backup of month. Do thorough checksum comparison".
    RSYNC_OPTIONS="${RSYNC_OPTIONS} -c"
fi

LOGFILE="${DEST}.log"

mkdir $DEST

echo "Create backup at $DEST relative to $LAST..."

for src_dir in ${SRC}; do
    echo "Backup directory ${src_dir}"
    src_relative=${src_dir#/}
    cmd="rsync ${RSYNC_OPTIONS}  --log-file=$LOGFILE $FILTER --link-dest=$LAST/ ${src_dir%/} $DEST"
    echo "$cmd"

    $cmd

    if test $? -ne 0; then
	echo "Rsync failed ..."
	exit 1
    fi
    echo ""
done 


echo "Print log..."
tail ${LOGFILE}

LOGTMP=/tmp/$(basename LOGFILE)
echo "Copy log to ${LOGTMP}"
cp ${LOGFILE} ${LOGTMP}

echo "Compute backup statistics..."
du -sh $BACKUP_DIR/*
df -h | grep ${MNT_DIR}

if [[ ${DO_UMOUNT} -eq 1 ]]; then
    echo "Unmount $BACKUP_DEVICE..."
    umount $MNT_DIR
    if test $? -ne 0; then
	echo "Failed ..."
	exit 1
    fi
else 
    echo "$BACKUP_DEVICE was already mounted. Do not umount."
fi

