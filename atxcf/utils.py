# -*- coding: utf-8 -*-

import csv


def append_csv_row(csv_filename, fields):
    """
    Appends row to specified csv file. 'fields' should be
    a list.
    """
    with open(csv_filename, 'ab') as f:
        writer = csv.writer(f)
        writer.writerow(fields)
