import argparse

from llm_tracekit.local_debugging.cli.list import list_llm_conversations
from llm_tracekit.local_debugging.cli.show import show_span
from llm_tracekit.local_debugging.cli.watch import watch
from llm_tracekit.local_debugging.filesystem_spans import FilesystemSpans


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--traces-directory",
        type=str,
        help="directory that holds trace files",
        default=None
    )

    subparsers = parser.add_subparsers(
        title="commands",
        metavar="<command>",
        dest="command",
        required=True,
    )

    subparsers.add_parser("list", parents=[common], help="list llm conversations")

    p_clear = subparsers.add_parser("show", parents=[common], help="show a single conversation")
    p_clear.add_argument("--id", help="the conversation id")

    subparsers.add_parser(
        "watch", parents=[common], help="follow a trace in real time"
    )

    p_clear = subparsers.add_parser("clear", parents=[common], help="clear all stored conversations")

    return parser

def main():
    args = build_parser().parse_args()

    if args.command == 'list':
        list_llm_conversations(args.traces_directory)
    elif args.command == 'show':
        show_span(args.traces_directory, args.id)
    elif args.command == 'watch':
        watch(args.traces_directory)
    elif args.command == "clear":
        filesystem_spans = FilesystemSpans(args.traces_directory)
        filesystem_spans.clear_all()
