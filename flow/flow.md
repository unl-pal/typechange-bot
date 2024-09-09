---
title: Workflow for "Understanding Developers' Addition and Removal of Type Annotations" (IRB 23988)
documentclass: scrartcl
classoption:
 - parskip=half
 - DIV=14
linkcolor: blue
papersize: letter
fontsize: 11pt
numbersections: true
---

At any time during the monitoring period, a person may submit an opt out command as a commit comment (at which point the [Participant Opts Out][] flow is followed).
They may likewise request removal of their data (and the [Participant Requests Removal Of Data][] flow is followed).

#### Note on Conventions and Assumptions {-}

In this document, comments made by our bot are marked with `(BOT COMMENT)` for clarity.
Upon deployment, these comments will not include this phrase, as GitHub marks bot actions automatically.

Additionally, we assume that we are dealing with projects which have agreed to participate in this project.

Finally, some small details (exact location of study website, the name of the bot) have not yet been determined.
In particular, in this document, the bot referred to as `@UNLPALBOTACCT` will be given a slightly different name.


# Start

A commit which adds or removes a type annotation has been detected.

 - If the committer is on the opt-out list, do nothing.
 - If the committer has consented, go to [Send Survey][]
 - If the committer is not listed, go to [Participant Not Listed][]

# Participant Not Listed

If already contacted, do nothing.

Else, obtain consent TODO

# Participant Opts Out

The participant has sent the `@UNLPALBOTACCT OPTOUT` command.

Place participant on opt-out list.

# Participant Consents

Record participant's consent information.

Go to [Send Survey][].

# Send Survey

TODO

# Participant Requests Removal Of Data

A participant has submitted the command `@UNLPALBOTACCT REMOVE`.
A record of the removal request, and opt-out is made.
Data than removal request, opt-out, and initial consent is removed from the server.
