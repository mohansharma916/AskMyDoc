# Engineering On-call Guide

How the Northwind Robotics platform team runs on-call. Northwind is a fictional company used as a test corpus.

## Rotation

Engineers on the platform team join a weekly on-call rotation once they have been at Northwind for three months. Shifts start on Monday at 10:00 local time and last one week. Each shift has a primary and a secondary on-call engineer. Shift swaps must be recorded in PagerDuty at least 48 hours in advance.

## Compensation

On-call engineers receive a stipend of 400 USD per week of on-call duty. Engineers who handle an incident lasting more than two hours between midnight and 06:00 may start work late the next day. Engineers who are paged on a public holiday receive one extra day of PTO.

## Response times

The primary on-call engineer must acknowledge pages within 15 minutes. If the primary does not acknowledge within 15 minutes, the page escalates to the secondary, and after a further 15 minutes to the engineering manager.

## Incident severity

| Severity | Definition | Update cadence |
| --- | --- | --- |
| SEV1 | Customer-facing outage or data loss | Every 30 minutes |
| SEV2 | Major feature degraded for many customers | Every 60 minutes |
| SEV3 | Minor degradation with a workaround | Daily |

SEV1 incidents require an incident commander and a dedicated communications lead. The status page must be updated within 20 minutes of declaring a SEV1.

## Postmortems

A blameless postmortem is required for every SEV1 and SEV2 incident. The postmortem draft is due within five working days of the incident being resolved. Action items from postmortems are tracked in Jira with the label postmortem and reviewed in the weekly operations meeting.

## Handover

At the end of each shift, the outgoing primary writes a handover note in the #oncall channel listing open incidents, noisy alerts and pending follow-ups.
