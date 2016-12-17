import os
import re
import ast
import sys
import shutil
import urllib
import urlparse
from ftplib import FTP, FTP_TLS

tobechecked = sys.argv[1]
totalsize = 0
maxitemsize = 209715200

if not os.path.exists('items'):
    os.makedirs('items')
if not os.path.exists('archive'):
    os.makedirs('archive')

def find_month_index(line_array):
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov" "Dec"]
    month_indices = []
    for month in months:
        if month in line_array:
            month_indices.append(line_array.index(month))
    return min(month_indices)

def fixurl(itemurl):
    #remove port number from url if it is equal to 21
    up = urlparse.urlparse(itemurl)
    if ":" in up.netloc:
        domain, port = up.netloc.split(":")
        if int(port) == 21:
            host = domain
        else:
            host = up.netloc
    else:
        host = up.netloc

    url_tuple = (up.scheme,host,up.path,up.params,up.params)

    return urlparse.urlunsplit(url_tuple)

with open(tobechecked, 'r') as file:
    ftps = file.read().splitlines()
    for ftp in ftps:
        ftp_up = urlparse.urlparse(ftp)

        ftp = ftp.strip()
        if ftp.lower().startswith("ftp://"):
            ftp = ftp[6::]
        if ftp.lower().startswith("ftps://"):
            ftp = ftp[7::]

        if ftp_up.scheme.lower() == "ftps":
            ftp_conn = FTP_TLS(ftp_up.netloc)
        else:
            ftp_conn = FTP(ftp_up.netloc)

        status = ftp_conn.login()
        if '230' not in status:
            print("ERROR: Failed to connect to FTP server. Status:{}".format(status))
            continue

        itemftps = []
        itemslist = []
        itemsizes = []


        startdir = ftp_up.netloc
        if not startdir.endswith('/'):
            startdir += '/'

        dirslist = [startdir]
        donedirs = []
        while all(dir not in donedirs for dir in dirslist):
            for dir in dirslist:
                dir = dir.replace('&#32;', '%20').replace('&amp;', '&')
                if re.search(r'&#[0-9]+;', dir):
                    raise Exception(dir)
                dir = dir.replace('#', '%23')

                for dir_derivative in (dir, "{}./".format(dir), "{}../".format(dir)):

                    ftp_dir = urlparse.urlunsplit((ftp_up.scheme,
                                                   ftp_up.netloc,
                                                   dir_derivative,
                                                   '',
                                                   ''))

                    if not ftp_dir + dir in itemslist:
                        itemslist.append(ftp_dir)
                        itemftps.append(ftp_up.netloc)
                        itemsizes.append(0)

                for match in re.findall(r'([^\/]+)', dir):
                    if '/' + match + '/' + match + '/' + match + '/' + match + '/' + match in dir:
                        break
                else:
                    if not dir in donedirs:

                        rel_dir = dir.replace(ftp_up.netloc,"")

                        ftp_dir = urlparse.urlunsplit((ftp_up.scheme,
                                                       ftp_up.netloc,
                                                       rel_dir,
                                                       '',
                                                       ''))

                        try:
                            ftp_conn.cwd(rel_dir)
                        except:
                            print("Couldn't get into: {}".format(rel_dir))

                        def ftp_list_callback(line):
                            global dirslist
                            global itemsizes
                            global itemslist
                            global dir

                            line_array = line.split()

                            fs_obj_name = " ".join(line_array[8:])


                            if line.startswith("d"):
                                if dir.endswith("/") == False:
                                    dir = "{}/".format(dir)

                                path = urlparse.urljoin(dir, fs_obj_name)
                                dirslist.append(path)
                                itemsizes.append(0)

                            elif line.startswith("-"):
                                path = urlparse.urljoin(dir, fs_obj_name)
                                if path.startswith("ftp://") == False and path.startswith("ftps://") == False:
                                    path = "ftp://{}".format(path)
                                print "file:{}".format(path)
                                itemslist.append(path)

                                # Size listing is always just before the Month
                                # So find the month index and subtract one to get size
                                month_index = find_month_index(line_array)
                                size = int(line_array[month_index-1])

                                itemsizes.append(size)

                                print "size:{}".format(size)

                            else:
                                return None

                        ftp_conn.retrlines('LIST', ftp_list_callback)

                        donedirs.append(dir)
        print "Done discovery, writing to disk..."

        totalitems = zip(itemftps, itemslist, itemsizes)
        archivelist = []
        newitems = []
        itemsize = 0
        itemnum = 0
        itemlinks = 0
        if os.path.isfile('archive/' + totalitems[0][0]):
            with open('archive/' + totalitems[0][0]) as file:
                archivelist = [list(ast.literal_eval(line)) for line in file]
        if os.path.isfile('archive/' + totalitems[0][0] + '-data'):
            with open('archive/' + totalitems[0][0] + '-data', 'r') as file:
                itemnum = int(file.read()) + 1
        for item in totalitems:
            if re.search(r'^(ftp:\/\/.+\/)[^\/]+\/', item[1]):
                if not (item[0], re.search(r'^(ftp:\/\/.+\/)[^\/]+\/', item[1]).group(1), 0) in totalitems:
                    totalitems.append((item[0], re.search(r'^(.+\/)[^\/]+\/', item[1]).group(1), 0))
                    totalitems.append((item[0], re.search(r'^(.+\/)[^\/]+\/', item[1]).group(1) + './', 0))
                    totalitems.append((item[0], re.search(r'^(.+\/)[^\/]+\/', item[1]).group(1) + '../', 0))
        for item in totalitems:
            itemurl = fixurl(item[1])
            if '&amp;' in itemurl or not [item[2], itemurl] in archivelist:
                newitems.append(item)
        for item in newitems:
            itemdir = re.search(r'^(ftp:\/\/.+\/)', item[1]).group(1)
            while True:
                if not (item[0], itemdir, 0) in newitems:
                    newitems.append((item[0], itemdir, 0))
                if re.search(r'^ftp:\/\/[^\/]+\/$', itemdir):
                    break
                itemdir = re.search(r'^(ftp:\/\/.+\/)[^\/]+\/', itemdir).group(1)
            itemurl = fixurl(item[1])
            with open('items/' + item[0] + '_' + str(itemnum), 'a') as file:
                file.write(itemurl + '\n')
                itemsize += item[2]
                totalsize += item[2]
                itemlinks += 1
                if itemsize > maxitemsize or newitems[len(newitems)-1] == item:
                    file.write('ITEM_NAME: ' + item[0] + '_' + str(itemnum) + '\n')
                    file.write('ITEM_TOTAL_SIZE: ' + str(itemsize) + '\n')
                    file.write('ITEM_TOTAL_LINKS: ' + str(itemlinks) + '\n')
                    itemnum += 1
                    itemsize = 0
                    itemlinks = 0
            if not [item[2], itemurl] in archivelist:
                with open('archive/' + item[0], 'a') as file:
                    if "'" in itemurl:
                        file.write(str(item[2]) + ", \"" + itemurl + "\"\n")
                    else:
                        file.write(str(item[2]) + ', \'' + itemurl + '\'\n')
            with open('archive/' + totalitems[0][0] + '-data', 'w') as file:
                if os.path.isfile('items/' + item[0] + '_' + str(itemnum-1)):
                    file.write(str(itemnum-1))
        try:
            urllib.urlopen('ftp://' + re.search(r'^([^\/]+)', ftp).group(1) + '/NONEXISTINGFILEdgdjahxnedadbacxjbc/')
        except Exception as error:
            dir_not_found = str(error).replace('[Errno ftp error] ', '')
            print(dir_not_found)

        try:
            urllib.urlopen('ftp://' + re.search(r'^([^\/]+)', ftp).group(1) + '/NONEXISTINGFILEdgdjahxnedadbacxjbc')
        except Exception as error:
            file_not_found = str(error).replace('[Errno ftp error] ', '')
            print(file_not_found)

        if os.path.isfile('items/' + re.search(r'^([^\/]+)', ftp).group(1) + '_dir_not_found'):
            os.remove('items/' + re.search(r'^([^\/]+)', ftp).group(1) + '_dir_not_found')
        if os.path.isfile('items/' + re.search(r'^([^\/]+)', ftp).group(1) + '_file_not_found'):
            os.remove('items/' + re.search(r'^([^\/]+)', ftp).group(1) + '_file_not_found')

        with open('items/' + re.search(r'^([^\/]+)', ftp).group(1) + '_dir_not_found', 'w') as file:
            file.write(dir_not_found)
        with open('items/' + re.search(r'^([^\/]+)', ftp).group(1) + '_file_not_found', 'w') as file:
            file.write(file_not_found)

        if not tobechecked == 'to_be_rechecked':
            with open('to_be_rechecked', 'a') as file:
                if os.path.isfile('to_be_checked'):
                    file.write('\n' + ftp)
                else:
                    file.write(ftp)

print(totalsize)
