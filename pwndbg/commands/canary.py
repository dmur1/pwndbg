from __future__ import annotations

import argparse

import pwndbg.auxv
import pwndbg.commands
import pwndbg.commands.telescope
import pwndbg.gdblib.memory
import pwndbg.gdblib.regs
import pwndbg.search
from pwndbg.color import message
from pwndbg.commands import CommandCategory


def canary_value():
    auxv = pwndbg.auxv.get()
    at_random = auxv.get("AT_RANDOM", None)
    if at_random is None:
        return None, None

    global_canary = pwndbg.gdblib.memory.pvoid(at_random)

    # masking canary value as canaries on the stack has last byte = 0
    global_canary &= pwndbg.gdblib.arch.ptrmask ^ 0xFF

    return global_canary, at_random


parser = argparse.ArgumentParser(description="Print out the current stack canary.")
parser.add_argument(
    "-a",
    "--all",
    action="store_true",
    help="Print out stack canaries for all threads instead of the current thread only.",
)


@pwndbg.commands.ArgparsedCommand(parser, command_name="canary", category=CommandCategory.STACK)
@pwndbg.commands.OnlyWhenRunning
def canary(all) -> None:
    global_canary, at_random = canary_value()

    if global_canary is None or at_random is None:
        print(message.error("Couldn't find AT_RANDOM - can't display canary."))
        return

    print(
        message.notice("AT_RANDOM = %#x # points to (not masked) global canary value" % at_random)
    )
    print(message.notice("Canary    = 0x%x (may be incorrect on != glibc)" % global_canary))

    found_canaries = False
    results_hidden = False
    global_canary_packed = pwndbg.gdblib.arch.pack(global_canary)
    thread_stacks = pwndbg.gdblib.stack.get()
    default_num_canaries_to_display = 2

    for thread in thread_stacks:
        thread_stack = thread_stacks[thread]

        stack_canaries = list(
            pwndbg.search.search(
                global_canary_packed, start=thread_stack.start, end=thread_stack.end
            )
        )

        if not stack_canaries:
            continue

        found_canaries = True

        print(message.success(f"Thread {thread}: Found valid canaries on stack."))

        num_canaries_to_display = len(stack_canaries)
        if not all:
            num_canaries_to_display = min(default_num_canaries_to_display, num_canaries_to_display)

        for stack_canary in stack_canaries[:num_canaries_to_display]:
            pwndbg.commands.telescope.telescope(address=stack_canary, count=1)

        if num_canaries_to_display < len(stack_canaries):
            results_hidden = True

    if found_canaries is False:
        print(message.warn("No valid canaries found on the stacks."))

    if results_hidden is True:
        print(message.warn("Additional results hidden. Use --all to see them."))
