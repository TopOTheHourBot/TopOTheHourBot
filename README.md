# TopOTheHourBot

TopOTheHourBot is a simple bot that only runs in HasanAbi's chat. It does one thing - that thing being to tally ad segue scores for an average.

![](./.github/assets/example.png)

The bot reads each incoming chat message searching for two items: an emote (DANKIES, PogO, or TomatoTime), and a score (a fraction whose denominator is 10, written vaguely like "X/10", where "X" can be any number).

If a high density of emotes and scores can be found within a certain timespan, TopOTheHourBot will send a notification to the channel, telling the average score.

## Further Details

Internally, the emotes and score are referred to as the "key" and "value", respectively - these terms will be used throughout the remainder of this section.

When the bot is online, it spends most of its time searching for a message that contains a value alone. When a value is first discovered, a background task is executed - known as the "aggregator".

The aggregator does a few things. When active, it waits for messages to be placed onto a queue, calculating the average value as more values arrive. During this process, it simultaneously counts the number of keys that can be found within the subset of messages that also contain a value. If a certain number of keys and values were counted by the aggregator, the channel will be notified of the average value.

When the aggregator is waiting for values to arrive, it is reliant on a timer that refreshes with every new arrival. This timer is about 9.5 seconds - meaning, chatters must be submitting their scores within 9.5 seconds of each other before the aggregator finishes waiting, and attempts to post a notification.

The notification is, again, only sent if a certain number of keys and values were found - known as the key and value "density". The densities change a lot with time, as they must be tuned for the behavior and popularity of the chat. As of the latest bot update, the key and value densities are 3 and 20, respectively.

## FAQ

### Can I submit multiple scores?

You can, yes. In prior iterations of the bot, you were unable to do so unless you had multiple accounts, but I ultimately decided that it'd be more fun if chatters could fight to skew the average in a certain direction.

### Can I submit a negative score? A score that's greater than 10? A decimal?

Yes, yes, and yes. Negative scores are treated as being equivalent to 0. Scores that are greater than 10 are treated as being equivalent to 10. In prior iterations of the bot, scores were not coerced to a value between 0 and 10 - this was an intentional design flaw to allow for funnier averages, but not many chatters recognized that negative values were also accepted (and thus, the average would always end up being extremely high - it wouldn't "balance out"). [This can be seen when Hasan first discovered the bot](https://clips.twitch.tv/ConfidentArtisticRutabagaKevinTurtle-LzPv2rHJROiM0bA_).

### Why does the bot chat normally sometimes?

The bot has some commands that are only usable by me and some friends. It used to have a command, called "$shadow", that would route whatever we're saying through the bot, without an indication that the message came from someone else. If you ever saw the bot chatting normally, it was one of us puppeteering it.

Twitch bots are also not like Discord bots - the user who created the bot's account may still login as the bot, and use the account as normal. This hasn't been done since the initial few days of the bot's deployment, however (there was one message sent in Hasan's chat, from me, that was done to test something).

### When does the bot run?

The bot will go online everyday at 2:00 PM Eastern (or, 11:00 AM Pacific in Hasan's time). It goes offline after 9 hours.

### How is the bot ran?

The bot currently runs on a [DigitalOcean Droplet](https://www.digitalocean.com/products/droplets) that executes the main.py script as a [cron job](https://en.wikipedia.org/wiki/Cron).

The bot has been moved to many different locations, however, and is likely to change again in the future.

### Why did the bot not send out a message at [some moment in time]?

Either the density of emotes and scores wasn't high enough, or its message was dropped by the Twitch server - the latter being the much more common scenario.

If you didn't already know: when a Twitch chat is moving quickly, messages will be served in "batches" - you might've noticed this yourself if you've ever seen a Twitch chat moving and stopping periodically. If you don't send a message while the chat is moving, your message is dropped by the Twitch servers to save on resources. This "drop" [can be seen on Chatterino](https://github.com/Chatterino/chatterino2/issues/1213), but not on the native Twitch web client. The native client "lies" to you by displaying your message on the screen when, in actuality, it may have never been sent.

### Are my messages kept somewhere?

Temporarily, yes - they have to be. Permanently, no.

In computing, there's this concept of volatile, and non-volatile memory. Volatile memory is stuff like random-access memory (or RAM) - this is typically for things that a program may need to remember for its lifespan, but may not necessarily require it in future lifespans. Non-volatile memory is stuff like hard drives - things that a program may, still, need to remember for its lifespan, but may also require it in future lifespans.

TopOTheHourBot runs solely on *volatile* memory - it will not know anything about what it has done in the past after it's taken offline and re-booted (which is done everyday). Meaning that the bot *cannot* keep messages or other information permanently.

## Requirements

The bot was written using Python 3.10. Its only external requirement is [TwitchIO](https://twitchio.dev/en/latest/) (version 2.4.0 at the time of development).

## Contributing

This personal mini-project has been considered finished for a while, but, if you have ideas on some features that could be added, feel free to open a pull request and/or issue.

This bot was made with simplicity in mind - please do not make and/or request a feature that would attract too much attention from users, enable the bot to spam chats, etc. Keep it civil.
