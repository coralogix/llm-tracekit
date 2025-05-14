import argparse

from llm_tracekit.local_debugging.cli.list import list_llm_conversations
from llm_tracekit.local_debugging.cli.show import show_span


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

    p_show = subparsers.add_parser("show", parents=[common], help="show a single conversation")
    p_show.add_argument("--id", help="the conversation id")

    p_watch = subparsers.add_parser(
        "watch", parents=[common], help="follow a trace in real time"
    )
    p_watch.add_argument("trace_name", help="file name of the trace to watch")

    return parser

def main():
    args = build_parser().parse_args()

    if args.command == 'list':
        list_llm_conversations(args.traces_directory)
    elif args.command == 'show':
        show_span(args.traces_directory, args.id)
    elif args.command == 'watch':
        pass
