# TopOTheHourBot

TopOTheHourBot is a simple bot that only runs in HasanAbi's chat. It does one thing - that thing being to tally ad segue scores for an average.

![](./.github/assets/example.png)

The bot reads each incoming chat message searching for "scores" - a fraction whose denominator is 10, written vaguely like "X/10", where "X" is any number. If a high density of scores can be found within a certain timespan, TopOTheHourBot will send a notification to the channel, telling the average score.

## FAQ

### Can I submit multiple scores?

You can, yes. In prior iterations of the bot, you were unable to do so unless you had multiple accounts, but I ultimately decided that it'd be more fun if chatters could fight to skew the average in a certain direction.

### Can I submit a negative score? A score that's greater than 10? A decimal?

Yes, yes, and yes. Negative scores are treated as being equivalent to 0. Scores that are greater than 10 are treated as being equivalent to 10. In prior iterations of the bot, scores were not coerced to a value between 0 and 10 - this was an intentional design flaw to allow for funnier averages, but not many chatters recognized that negative values were also accepted (and thus, the average would always end up being extremely high - it wouldn't "balance out"). [This can be seen when Hasan first discovered the bot](https://clips.twitch.tv/ConfidentArtisticRutabagaKevinTurtle-LzPv2rHJROiM0bA_).

### Why does the bot chat normally sometimes?

The bot has some commands that are only usable by me and some friends. It used to have a command, called "$shadow", that would route whatever we're saying through the bot, without an indication that the message came from someone else. If you ever saw the bot chatting normally, it was one of us puppeteering it.

Twitch bots are also not like Discord bots - the user who created the bot's account may still login as the bot, and use the account as normal. This hasn't been done since the initial few days of the bot's deployment, however (there was one message sent in Hasan's chat, from me, that was done to test something).

In the past, I've also made small changes to have it reply to some friends under particular conditions.

### When does the bot run?

The bot will go online everyday at 2:00 PM Eastern (or, 11:00 AM Pacific in Hasan's time). It goes offline after 9.5 hours.

### How is the bot ran?

The bot currently runs on a [DigitalOcean Droplet](https://www.digitalocean.com/products/droplets) that executes the main.py script as a [cron job](https://en.wikipedia.org/wiki/Cron). The bot has been moved to many different locations, however, and is likely to change again in the future.

### Why did the bot not send out a message at [some moment in time]?

Either the score density wasn't high enough, or its message was dropped by Twitch servers - the latter being the much more common scenario.

If you didn't already know: when a Twitch chat is moving quickly, messages get served in batches (this is why you might've seen it moving and stopping periodically). If you don't send a message while the chat is moving, your message is dropped by the Twitch servers to save on resources. This "drop" [is visualized by Chatterino](https://github.com/Chatterino/chatterino2/issues/1213), but not on the native Twitch web client. The native client "lies" to you by displaying your message on the screen when, in actuality, it may have never been sent.

### Why does the bot not do [this thing] anymore?

I go back-and-forth on ideas a lot. Many things have changed in regard to the bot's message formats and administrative features. Some of these things were scrapped for performance reasons (keeping the bot online costs money), and others simply because I didn't want the bot to do that thing anymore.

### Why does the bot have [this name color]?

I change its name color for certain holiday seasons. Its "default" name color is the pink that is offered to all users of Twitch - it's a small homage to a friend in chat.

### Are my messages kept somewhere?

Temporarily, yes - they have to be. Permanently, no.

In computing, there's this concept of volatile, and non-volatile memory. Volatile memory is stuff like random-access memory (or RAM) - this is typically for things that a program may need to remember for its lifespan, but may not necessarily require it in future lifespans. Non-volatile memory is stuff like hard drives - things that a program may, still, need to remember for its lifespan, but may also require it in future lifespans.

TopOTheHourBot runs solely on *volatile* memory - it will not know anything about what it has done in the past after it's taken offline and re-booted (which is done everyday). Meaning that the bot *cannot* keep messages or other information permanently.

## Requirements

The bot was written using Python 3.10. Its only external requirement is [TwitchIO](https://twitchio.dev/en/latest/) (version 2.4.0 at the time of development).

## Contributing

This personal mini-project has been considered finished for a while, but, if you have ideas on some features that could be added, feel free to open a pull request and/or issue. Be warned, however - I refactor the code a lot.

This bot was made with simplicity in mind - please do not make and/or request a feature that would attract too much attention from users, enable the bot to spam chats, etc. Keep it civil.

## Etc.

This bot is not associated with any other projects pertaining to Hasan's ad segues. There exists another bot, "Hasanabi_Segways" (yes, that is how it is spelled), that has no relation to this project, and whose owner I do not know.
