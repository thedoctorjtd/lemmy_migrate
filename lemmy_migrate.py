import argparse
import configparser
import json
import logging
import os
import sys
from logging import handlers

from lemmy import Lemmy

logger = logging.getLogger(__name__)


def get_config(cfile):
    config = configparser.ConfigParser(interpolation=None)
    read = config.read(cfile)
    if not read:
        logger.warning(f"Could not read config {cfile}!")
        sys.exit(1)

    accounts = {i: dict(config.items(i)) for i in config.sections()}
    return accounts


def get_args():
    parser = argparse.ArgumentParser(
        prog="lemmy_migrate",
        description=f"Migrate subscribed " f"communities from one account " f"to another",
    )

    parser.add_argument("-c", required=True, help="Path to config file", metavar="<config file>")
    parser.add_argument(
        "-u",
        help="use to update main account subscriptions",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-e", help="Export main account subscriptions to json", metavar="<export file>"
    )
    parser.add_argument("-i", help="Import subscriptions from json file", metavar="<import file>")
    args = parser.parse_args()
    return args


def sync_subscriptions(src_acct: Lemmy, dest_acct: Lemmy, from_backup):
    logger.info(
        f"[ Subscribing {dest_acct.site_url} to new communities from " f"{src_acct.site_url} ]"
    )
    logger.info(" Getting list of subscribed communities from the two communities")
    if from_backup:
        src_comms = from_backup
    else:
        src_comms = src_acct.get_communities()
    logger.info(
        f" {len(src_comms)} subscribed communities found in the source" f" {src_acct.site_url}"
    )

    dest_comms = dest_acct.get_communities()
    logger.info(
        f" {len(dest_comms)} subscribed communities found in the target" f" {dest_acct.site_url}"
    )

    new_communities = [c for c in src_comms if c not in dest_comms]

    if new_communities:
        logger.info(f" Subscribing to {len(new_communities)} new communities")
        dest_acct.subscribe(new_communities)


def write_backup(account: Lemmy, output: str) -> None:
    comms = account.get_communities()
    try:
        with open(output, "w") as f:
            json.dump({account.site_url: list(comms)}, f, indent=4)
    except Exception as e:
        logger.exception(f"  Error exporting file {output}.", exc_info=e)
    else:
        logger.info(f"  {len(comms)} Subscriptions backed up to {output}.")


def read_backup(file: str) -> set | None:
    comms = None
    try:
        with open(file, "r") as f:
            data = json.load(f)
            comms = {c for k, v in data.items() for c in v}
    except Exception as e:
        logger.exception(f"Failed to read import list {file}.", exc_info=e)
        logger.info("Check your import list or run again without the import flag.")
        sys.exit(1)  # exit if import file is bad as to prevent unintended behavior

    return comms


def main():
    cfg = get_args()
    accounts = get_config(cfg.c)

    # source site
    logger.info(f"[ Getting Main Account info -" f" {accounts['Main Account']['site']} ]")
    main_lemming = Lemmy(accounts["Main Account"]["site"])
    try:
        main_lemming.login(accounts["Main Account"]["user"], accounts["Main Account"]["password"])
    except Exception as e:
        logger.error("Unable to login to main account. Check your credentials and try again.")
        sys.exit(1)
    else:
        logger.info("Main account login successful.")

    accounts.pop("Main Account", None)

    # export subscriptions
    if cfg.e:
        write_backup(main_lemming, cfg.e)
        return

    # import communites backed up if specified
    comms_backup = None
    if cfg.i and not cfg.u:
        comms_backup = read_backup(cfg.i)

    # sync main account communities to each account
    for acc in accounts:
        logger.info(f"[ Getting {acc} - {accounts[acc]['site']} ]")
        new_lemming = Lemmy(accounts[acc]["site"])
        try:
           new_lemming.login(accounts[acc]["user"], accounts[acc]["password"])
        except Exception as e:
            logger.debug(f"Unable to login to {acc}.", exc_info=e)
            logger.warning(f"Unable to login to {acc}. Check your credentials and try again.")
            logger.warning(f"{e}")
            logger.info("Continuing to next account.")
            continue

        if cfg.u:
            logger.info(" Update main flag set. Updating main account subscriptions.")
            src = new_lemming
            dest = main_lemming
        else:
            src = main_lemming
            dest = new_lemming

        sync_subscriptions(src, dest, comms_backup)


if __name__ == "__main__":
    fileDir = os.path.dirname(os.path.realpath(__file__))
    logFile = os.path.join(fileDir, "lemmy_migrate.log")

    fHandler = handlers.RotatingFileHandler(
        logFile, encoding="utf-8", maxBytes=5000000, backupCount=1
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[fHandler, logging.StreamHandler()],
        force=True,
    )
    logger.info("Starting Lemmy Migrate")
    main()
