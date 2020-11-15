#!/usr/bin/env python3
import os.path
import pandas as pd
import sys
import getopt
import re
import logging
import analyze
import json

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
logger.addHandler(handler)


def load_json_file(path: str):
    """
    Loads and parses the content of a json file.
    :param path:
    :return:
    """

    if not os.path.isfile(path):
        return None

    with open(path, 'r') as file:
        try:
            return json.load(file)
        except json.JSONDecodeError as e:
            if e.msg != "Extra data":
                logger.exception("Failed to load json file '%s'" % path)
                return None

            # Read only first object from file, ignore extra data
            file.seek(0)
            json_str = file.read(e.pos)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.exception("Failed to read json file '%s'" % path)
                return None



def parse_quic_goodput(result_set_path):
    """
    Parse the goodput of the QUIC measurements from the log files in the given folder.
    :param result_set_path:
    :return:
    """

    logger.info("Parsing QUIC goodput from log files")
    df = pd.DataFrame(columns=['run', 'second', 'bits'])

    for file_name in os.listdir(result_set_path):
        path = os.path.join(result_set_path, file_name)
        if not os.path.isfile(path):
            logger.debug("'%s' is not a file, skipping")
            continue
        match = re.search(r"^(\d+)_quic_goodput\.txt$", file_name)
        if not match:
            continue

        logger.debug("Parsing '%s'", file_name)
        run = int(match.group(1))
        with open(path) as file:
            for line in file:
                line_match = re.search(r"^second (\d+):.*\((\d+) bytes received\)", line.strip())
                if not line_match:
                    continue

                df = df.append({
                    'run': run,
                    'second': int(line_match.group(1)),
                    'bits': int(line_match.group(2)) * 8
                }, ignore_index=True)

    return df


def parse_quic_cwnd_evo(result_set_path):
    """
    Parse the congestion window evolution of the QUIC measurements from the log files in the given folder.
    :param result_set_path:
    :return:
    """

    logger.info("Parsing QUIC congestion window evolution from log files")
    df = pd.DataFrame(columns=['run', 'second', 'cwnd'])

    for file_name in os.listdir(result_set_path):
        path = os.path.join(result_set_path, file_name)
        if not os.path.isfile(path):
            logger.debug("'%s' is not a file, skipping")
            continue
        match = re.search(r"^(\d+)_quic_cwnd_evo\.txt$", file_name)
        if not match:
            continue

        logger.debug("Parsing '%s'", file_name)
        run = int(match.group(1))
        with open(path) as file:
            for line in file:
                line_match = re.search(r"^connection.*second (\d+).*send window: (\d+)", line.strip())
                if not line_match:
                    continue

                df = df.append({
                    'run': run,
                    'second': int(line_match.group(1)),
                    'cwnd': int(line_match.group(2))
                }, ignore_index=True)

    return df


def parse_tcp_cwnd_evo(result_set_path):
    """
    Parse the congestion window evolution of the TCP measurements from the log files in the given folder.
    :param result_set_path:
    :return:
    """

    logger.info("Parsing TCP congestion window evolution from log files")
    df = pd.DataFrame(columns=['run', 'second', 'cwnd'])

    for file_name in os.listdir(result_set_path):
        path = os.path.join(result_set_path, file_name)
        if not os.path.isfile(path):
            logger.debug("'%s' is not a file, skipping")
            continue
        match = re.search(r"^(\d+)_tcp_cwnd_evo\.json$", file_name)
        if not match:
            continue

        logger.debug("Parsing '%s'", file_name)
        run = int(match.group(1))

        results = load_json_file(path)
        if results is None:
            logger.warning("'%s' has no content" % path)
            continue

        for interval in results['intervals']:
            df = df.append({
                'run': run,
                'second': round(interval['sum']['start']),
                'cwnd': int(interval['streams'][0]['snd_cwnd'])
            }, ignore_index=True)

    return df


def measure_folders(root_folder):
    for folder_name in os.listdir(root_folder):
        path = os.path.join(root_folder, folder_name)
        if not os.path.isdir(path):
            logger.debug("'%s' is not a directory, skipping", folder_name)
            continue

        match = re.search(r"^(GEO|MEO|LEO)_r(\d+)mbit_l(\d+(?:\.\d+)?)_q(\d+(?:\.\d+)?)(?:_([a-z]+))?$", folder_name)
        if not match:
            logger.info("Directory '%s' doesn't match, skipping", folder_name)
            continue

        delay = match.group(1)
        rate = int(match.group(2))
        loss = float(match.group(3)) / 100.0
        queue = float(match.group(4))
        pep = match.group(5) if match.group(5) else "none"
        yield folder_name, delay, rate, loss, queue, pep


def parse(in_dir="~/measure"):
    logger.info("Parsing measurement results in '%s'", in_dir)
    df_goodput = pd.DataFrame(columns=['protocol', 'pep', 'delay', 'rate', 'loss', 'queue', 'run', 'second', 'bits'])
    df_cwnd_evo = pd.DataFrame(columns=['protocol', 'pep', 'delay', 'rate', 'loss', 'queue', 'run', 'second', 'cwnd'])

    for folder_name, delay, rate, loss, queue, pep in measure_folders(in_dir):
        logger.info("Parsing files in %s", folder_name)
        path = os.path.join(in_dir, folder_name)

        # QUIC goodput
        df = parse_quic_goodput(path)
        df['protocol'] = 'quic'
        df['pep'] = pep
        df['delay'] = delay
        df['rate'] = rate
        df['loss'] = loss
        df['queue'] = queue
        df_goodput = df_goodput.append(df, ignore_index=True)

        # QUIC congestion window evolution
        df = parse_quic_cwnd_evo(path)
        df['protocol'] = 'quic'
        df['pep'] = pep
        df['delay'] = delay
        df['rate'] = rate
        df['loss'] = loss
        df['queue'] = queue
        df_cwnd_evo = df_cwnd_evo.append(df, ignore_index=True)

        # TCP congestion window evolution
        df = parse_tcp_cwnd_evo(path)
        df['protocol'] = 'tcp'
        df['pep'] = pep
        df['delay'] = delay
        df['rate'] = rate
        df['loss'] = loss
        df['queue'] = queue
        df_cwnd_evo = df_cwnd_evo.append(df, ignore_index=True)

    # Fix data types
    df_goodput['rate'] = pd.to_numeric(df_goodput['rate'])
    df_goodput['loss'] = pd.to_numeric(df_goodput['loss'])
    df_goodput['queue'] = pd.to_numeric(df_goodput['queue'])
    df_goodput['run'] = pd.to_numeric(df_goodput['run'])
    df_goodput['second'] = pd.to_numeric(df_goodput['second'])
    df_goodput['bits'] = pd.to_numeric(df_goodput['bits'])

    df_cwnd_evo['rate'] = pd.to_numeric(df_cwnd_evo['rate'])
    df_cwnd_evo['loss'] = pd.to_numeric(df_cwnd_evo['loss'])
    df_cwnd_evo['queue'] = pd.to_numeric(df_cwnd_evo['queue'])
    df_cwnd_evo['run'] = pd.to_numeric(df_cwnd_evo['run'])
    df_cwnd_evo['second'] = pd.to_numeric(df_cwnd_evo['second'])
    df_cwnd_evo['cwnd'] = pd.to_numeric(df_cwnd_evo['cwnd'])

    return df_goodput, df_cwnd_evo


def main(argv):
    in_dir = "~/measure"
    out_dir = "."

    try:
        opts, args = getopt.getopt(argv, "i:o:", ["input=", "output="])
    except getopt.GetoptError:
        print("parse.py -i <inputdir> -o <outputdir>")
        sys.exit(2)

    for opt, arg in opts:
        if opt in ("-i", "--input"):
            in_dir = arg
        elif opt in ("-o", "--output"):
            out_dir = arg

    df_goodput, df_cwnd_evo = parse(in_dir)

    if not os.path.exists(out_dir):
        os.mkdir(out_dir)
    if not os.path.isdir(out_dir):
        logger.error("Output directory is not a directory! Skipping analysis")
        return

    analyze.analyze_goodput(df_goodput, out_dir=out_dir)
    analyze.analyze_cwnd_evo(df_cwnd_evo, out_dir=out_dir)


if __name__ == '__main__':
    main(sys.argv[1:])
