# GCSEDiscordBot (Adam-Bot)

![Adam-Bot logo](https://cdn.discordapp.com/avatars/525083089924259898/c16a8482a4151d0bc291bf5a2e61acf0.webp?size=256)

Python code that runs "Adam-Bot", mainly for use in the GCSE 9-1 Discord server. If you have an issue, feature request, or would like to report a bug, please feel free to [raise an issue](https://github.com/adampy/gcsediscordbot/issues/new/choose).

The bot is hosted on [Heroku](https://www.heroku.com), and uses a [free-tier PostgreSQL database](https://elements.heroku.com/addons/heroku-postgresql) (maximum 10,000 total rows limit and 1GB maximum storage).

This guide contains:
* [Preliminary note](#Preliminary-note)
* [Information on every cog](#Cogs)
* [The most recent database schema](#Database-Schema)
* [Contributors](Contributors)

# Preliminary note
For future reference, maintainability, and the fact that database information/schemas are not included in the program, here are some notes that should be read before editing a particular file, so that you become accustomed to the workflow.

Thanks to all contributors:
* [@adampy](https://github.com/adampy)
* [@monkeyboy2805](https://github.com/monkeyboy2805)
* [@xp3d1](https://github.com/xp3d1)
* [@safwaan786](https://github.com/safwaan786)

# Cogs
## Demographics
Used for storing demographic data about a server showing trends in a role frequency-time graph. This works by having two database tables, one for storing the demographic sample information, e.g. what roles to sample from what guilds, and the actual demographic samples. Demographic samples are taken at midnight, every day. The demographic charts (`-demographics chart`) are shown using `matplotlib`.

## Member
Used for miscellaneous commands ranging from -userinfo, to -bruhs. There is no real format to this file yet, and it mostly relates to the commands that a member can perform without needing any extra permissions. The -remind command also is stored here. *(This module may be decomposed in the future)*

## Moderation
Contains moderation commands, such as kicks, bans, and mutes. Slowmodes, and the jail command reside here too. The advance command, that advances everyones year (e.g. Y9 -> Y10) is here and has admin perms.

## Private
Used for functionaltiy and commands that feature in private servers.

## QuestionOTD
The module that contains all of the commands relating to QOTDs (commonly known as question of the day). People with a "QOTD" role have permissions to view, delete, and pick OQTDs. People without these roles can only submit QOTDs (2 per 24h).

QOTDs are stored in the database in this table with the following schema.

## Reputation
The reputation module, as the name gives away, is used for storing reputation points. Reputation points, or "reps", are given in the server when some user helps another user. The `-rep leaderboard` command is guild-specific, meaning that it can be executed in any guild, and includes all members that are part of that guild. The same mechanics are in use when checking someone's leaderboard position with the `-rep check` command. `-rep data` is a command that allows people to see the distribution of reps in the server. The amount of reps is on the x-axis, and the number of people with that specific number of rep is on the y-axis. This, again, uses `matplotlib`. 

# Database schema
The following describes the database schema, as of 27/03/2021.

##  qotd
Field name | Type | Constraints
-----------|------|--------------
id | int | SERIAL PRIMARY KEY
question | varchar(255) | 
submitted_by | varchar(255)
submitted_at | timestamptz | NOT NULL DEFAULT now()

## todo
Field name | Type | Constraints
-----------|------|--------------
id | int | SERIAL PRIMARY KEY
todo_id | int
todo_time | timestamptz
member_id | bigint

## support
Field name | Type | Constraints
-----------|------|--------------
id | int | SERIAL PRIMARY KEY
member_id | bigint
staff_id | bigint
started_at | timestamptz

## remind
Field name | Type | Constraints
-----------|------|--------------
id | int | SERIAL PRIMARY KEY
member_id | bigint
reminder_time | timestamptz
reminder | varchar(255)
created_at | timestamptz

## warn
Field name | Type | Constraints
-----------|------|--------------
id | int | SERIAL PRIMARY KEY
member_id | bigint
staff_id | bigint
warned_at | timestamptz | NOT NULL DEFAULT now()
reason | varchar(255)

## rep
Field name | Type | Constraints
-----------|------|--------------
member_id | bigint
reps | int

## invite
Field name | Type | Constraints
-----------|------|--------------
inviter | bigint
code | varchar(255)
uses | int
max_uses | int
created_at | timestamptz
max_age | bigint

## variables
Field name | Type | Constraints
-----------|------|--------------
variable | varchar(255)
value | varchar(1023)

## demographic_roles
Field name | Type | Constraints
-----------|------|--------------
id | int | SERIAL PRIMARY KEY
sample_rate | int | NOT NULL DEFAULT 1
guild_id | bigint | NOT NULL
role_id | bigint | NOT NULL

## demographic_samples
Field name | Type | Constraints
-----------|------|--------------
n | int | NOT NULL DEFAULT 0
taken_at | timestamptz | NOT NULL DEFAULT now()
role_reference | int | NOT NULL

This table has a foreign key relation to demographic roles in the `demographic_roles` table. It is declared as:
```postgres
CONSTRAINT fk_role_reference 
    FOREIGN KEY (role_reference)
        REFERENCES demographic_roles(id)
        ON DELETE CASCADE
```

## ping
Field name | Type | Constraints
-----------|------|--------------
member_id | bigint

## classroom
Field name | Type | Constraints
-----------|------|--------------
section | int
gid | varchar(255)
name | varchare(255)
