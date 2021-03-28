# GCSEDiscordBot (Adam-Bot)

![Adam-Bot logo](https://cdn.discordapp.com/avatars/525083089924259898/c16a8482a4151d0bc291bf5a2e61acf0.webp?size=256)

Python code that runs "Adam-Bot", mainly for use in the GCSE 9-1 Discord server. If you have an issue, feature request, or would like to report a bug, please feel free to [raise an issue](https://github.com/adampy/gcsediscordbot/issues/new/choose).

The bot is hosted on [Heroku](https://www.heroku.com), and uses a [free-tier PostgreSQL database](https://elements.heroku.com/addons/heroku-postgresql) (maximum 10,000 total rows limit and 1GB maximum storage).

This guide contains:
* [Preliminary note](#Preliminary-note)
* [TODOs](#Todo)
* [Information on every cog](#Cogs)
* [The most recent database schema](#Database-Schema)

# Preliminary note
For future reference, maintainability, and the fact that database information/schemas are not included in the program, here are some notes that should be read before editing a particular file, so that you become accustomed to the workflow.

I'd like to give a special thanks to all who have contributed to the bot :wave: :clap: :
* [@adampy](https://github.com/adampy)
* [@monkeyboy2805](https://github.com/monkeyboy2805)
* [@xp3d1](https://github.com/xp3d1)
* [@safwaan786](https://github.com/safwaan786)

# Todo
To see the current roadmap for the bot, please see [here](https://github.com/adampy/gcsediscordbot/projects/1).

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

## Spotify
This is a seperate cog used for the `-spotify` command. It can be used to access someone's current Spotify information, e.g. party ID, current song, etc. It has been placed in a seperate cog simply for readability and maintainability.

## Support
The support cog is used to confidentially link members with the staff team. The `SupportConnection` class is used to store individual support connections, and the `SupportConnectionManager` is used to store all of the support connections, whether they are open or not. Every 5 seconds, or so, a method is used to access all of the support tickets.

When a new support connection is created, there is a message put into a support log channel, alerting staff members to the new support connection. When referencing the support connection to regular server members the phrase: (support) ticket is used, as this is popular terminology. The support tickets also have typing presence, so when a member is typing the staff can see, and when staff are typing the member can see. This is useful for seeing that the other party is active, and not AFK.

## Trivia
The trivia cog is used to quiz meembers when they do the `-trivia start` command. It works by getting the trivia data from a [public repo](https://github.com/adampy/trivia) and then asking those questions when a user wants that topic.

## WaitingRoom
WaitingRoom cog is used for verifying members into the server. The `-y9`, `-y10`, `-y11`, `-postgcse` commands are used to verify people, giving them both the Members role as well as the respective year. There is additional functionality when dealing with *lurkers*. *Lurkers* are defined as people who are currently in the verification channel without a role because they have not given their year. There is functionality for kicking all *lurkers* that have been in the server for more than 7 days, as well as sending them all a DM aasking for their year.

As well as this, there are commands to change the welcome message that the bot produces when someone new joins the server. This can be done using the `-editwelcome` commands, where the channel and the message can both be changed. In the message, channels can either be referenced normally (#channel), or using the syntax `C<channel_id>`. Roles are mentioned the same way: either using @role_name, or `R<role_id>`. 

The welcome message, and the welcome channel, are both stored in the `variables` table in the database. The channel is under the field `welcome_channel`, and the message is under `welcome_msg`.

## Warnings
This cog is for moderation, and was originally within the Moderation cog, but I had split it out making the code easier to read. Warnings are given by staff and then can be viewed using the `-warns` command. When a member does this, they can only see their own warnings, but when a staff member does this by default it views everyones warnings. For a staff member to view their own warnings, the must do `-warns @themself`. Warnings can be removed by a staff member using the `-warnremove` command.

# Database schema
The following describes the database schema, as of 28/03/2021.

##  qotd
Field name | Type | Constraints
-----------|------|--------------
id | int | SERIAL PRIMARY KEY
question | varchar(255) | 
submitted_by | varchar(255)
submitted_at | timestamptz | NOT NULL DEFAULT now()

<br>

## todo
Field name | Type | Constraints
-----------|------|--------------
id | int | SERIAL PRIMARY KEY
todo_id | int
todo_time | timestamptz
member_id | bigint

<br>

## support
Field name | Type | Constraints
-----------|------|--------------
id | int | SERIAL PRIMARY KEY
member_id | bigint
staff_id | bigint
started_at | timestamptz

<br>

## remind
Field name | Type | Constraints
-----------|------|--------------
id | int | SERIAL PRIMARY KEY
member_id | bigint
reminder_time | timestamptz
reminder | varchar(255)
created_at | timestamptz

<br>

## warn
Field name | Type | Constraints
-----------|------|--------------
id | int | SERIAL PRIMARY KEY
member_id | bigint
staff_id | bigint
warned_at | timestamptz | NOT NULL DEFAULT now()
reason | varchar(255)

<br>

## rep
Field name | Type | Constraints
-----------|------|--------------
member_id | bigint
reps | int

<br>

## invite
Field name | Type | Constraints
-----------|------|--------------
inviter | bigint
code | varchar(255)
uses | int
max_uses | int
created_at | timestamptz
max_age | bigint

<br>

## variables
Field name | Type | Constraints
-----------|------|--------------
variable | varchar(255)
value | varchar(1023)

<br>

## demographic_roles
Field name | Type | Constraints
-----------|------|--------------
id | int | SERIAL PRIMARY KEY
sample_rate | int | NOT NULL DEFAULT 1
guild_id | bigint | NOT NULL
role_id | bigint | NOT NULL

<br>

## demographic_samples
Field name | Type | Constraints
-----------|------|--------------
n | int | NOT NULL DEFAULT 0
taken_at | timestamptz | NOT NULL DEFAULT now()
role_reference | int | NOT NULL

<br>

This table has a foreign key relation to demographic roles in the `demographic_roles` table. It is declared as:
```postgres
CONSTRAINT fk_role_reference 
    FOREIGN KEY (role_reference)
        REFERENCES demographic_roles(id)
        ON DELETE CASCADE
```

<br>

## ping
Field name | Type | Constraints
-----------|------|--------------
member_id | bigint

<br>

This table is deprecated, and not currently used for anything. It was used for the `-toggle1738` command which has not been used for over a year.

<br>

## classroom
Field name | Type | Constraints
-----------|------|--------------
section | int
gid | varchar(255)
name | varchare(255)

<br>

This table is deprecated, and not currently used for anything in the GCSE 9-1 server.
