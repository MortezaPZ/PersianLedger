# Answers to the review questions

Version 0.5.0 notes, kept because later builds still follow these rules.

## Account statement versus party statement

Same engine, two directions.

| | Account statement | Party statement |
| --- | --- | --- |
| Start from | One account | One detail (a person or a project) |
| Shows | Every movement of that account, whoever the party is | Every movement of that party, in every account |
| Account column | No. Every row is the same account | Yes |
| Question it answers | What did the euro cash account do? | What does this company owe us in total? |

## What a floating-detail group is for

A group classifies details and does two jobs.

1. Input control. Each subsidiary account allows specific groups. The cash account accepts the cash group, so a person cannot be posted as a cash box by mistake.
2. Grouped reports. A report can say "only projects" or "only people".

## Can one detail code sit in several groups?

Yes. The form has a primary group, which drives the suggested code, and any number of extra memberships. "Project A" can be in Projects and in Cost centers without being defined twice. One record, one code, one balance.

The primary group is itself a membership. It appears in the extra-membership list as checked and disabled, so it is not mistaken for a separate group.

A detail never points directly at a subsidiary account. The chain is: detail is a member of a group, and a subsidiary account allows that group on slot 1 or slot 2. The detail form lists the subsidiary accounts that currently accept any of its groups. That list updates when the memberships change.

Default groups: people, cash and banks, projects, cost centers. Add more on the floating-detail screen.

The link from group to account is on the chart: select a subsidiary, edit, and set the groups allowed on detail 1 and detail 2. The tree also shows those slots under the subsidiary.

## Detail 1 and detail 2

A line can carry two analytical labels. They are not different kinds of record. The usual split:

- Detail 1 is the party: person, cash, or bank. Where the money came from or went.
- Detail 2 is the allocation: project or cost center. Which job the amount belongs to.

One line then feeds both the party's statement and the project's cost report.

## Reporting a detail that is in several groups

The group box on the account statement, trial balance, journal, and party statement is a multi-select.

- Nothing checked: no filter.
- One group: only that group's rows.
- Several groups: rows that belong to any of them.

A filtered trial balance is a slice. Its debit and credit totals do not have to match. The unfiltered trial balance does.

## How to record project receipts and costs

The project is a detail in the Projects group, used in slot 2. It is not a new chart account for every project.

| What | Where |
| --- | --- |
| Money in | Cash or bank, detail 1 = that cash account, detail 2 = the project |
| Still owed by the client | Receivables, detail 1 = the client, detail 2 = the project |
| Cost | The expense account, detail 2 = the project |

Then: project costs from the expense account filtered to the project, receipts from the cash account filtered to the project, and both together from the party statement for that project.

## Document type

A label for the document list and for filters. It does not change calculations and it does not create lines. Use the general type when unsure. The reversing and correcting types are set by the application.

## Sample project

The demo database includes the project documents so the three reports above can be opened without retyping them. Amounts in that sample are stored per currency. They are not converted.
