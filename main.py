"""Command line front end: python main.py "how much did we spend on cloud in Q1?" """

import sys

from agent import run_agent

DEFAULT_QUESTION = "Which vendor cost us the most, and what share of total spend was it?"


def main(argv):
    question = " ".join(argv[1:]) or DEFAULT_QUESTION
    print("Q:", question)
    answer = run_agent(question, trace=lambda line: print("   .", line))
    print("A:", answer)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
