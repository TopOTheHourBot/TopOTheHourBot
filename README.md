# TopOTheHourBot

TopOTheHourBot is a simple bot that only runs in HasanAbi's chat. It does one thing - that thing being to tally ad segue scores for an average.

![](./assets/example.png)

The bot reads each incoming chat message searching for two items: an emote (DANKIES, PogO, or TomatoTime), and a score (a fraction whose denominator is 10, written vaguely like "X/10", where "X" can be any number).

The ordering of the emote and score does not matter, and the message may contain other content so long as the two things appear somewhere within the message. When such a message is first discovered, using an emote alongside a score becomes unnecessary - a message that contains a score alone will be counted towards the average.

## In-Depth Details

Internally, the emote and score are referred to as the "key" and "value", respectively - these terms will be used throughout the remainder of this section.

When the bot is online, it spends most of its time searching for a message that contains *both* a key and value. When there is a message that fulfills this criteria, an averaging phase is started. When an averaging phase is active, the key is no longer required.

Values are internally kept as [floating point numbers](https://docs.python.org/3/library/functions.html#float). When a value is matched, it is put onto a queue to be tallied by an averaging function that runs in the background. This averaging function continuously waits for values to be placed onto the queue in intervals of ~9 seconds (referred to as the "decay time"). When values can no longer be found, the waiting process ends, and the average is calculated from the values it had collected.

The bot will send a message that contains the average if there were at least 20 unique chatters that submitted a matchable value. The format of its message is, roughly:

```
DANKIES 🔔 <chatter count> rated this ad segue an average of <average score>/10 - <splash> <emote>
```

The `<splash>` and `<emote>` fields vary depending on how high/low the average was, and if the average was the highest it had seen during its runtime. There are 4 possible splash fields, and 12 possible emotes (6 positive and 6 negative).

## FAQ

### Can I submit multiple scores?

The bot will use the first score it has seen from you during an averaging phase - your subsequent scores are ignored. If you wanted to submit multiple scores in an effort to skew the average, you'd need multiple accounts.

Submitting multiple scores will, however, allow more chatters to contribute one for themselves (since it refreshes the decay time).

### Can I submit a negative score? A score that's greater than 10? A decimal?

Yes, yes, and yes. Negative scores are treated as being equivalent to 0. Scores that are greater than 10 are treated as being equivalent to 10. In prior iterations of the bot, scores were not coerced to a value between 0 and 10 - this was an intentional design flaw to allow for funnier averages, but not many chatters recognized that negative values were also accepted (and thus, the average would always end up being extremely high - it wouldn't "balance out"). [This can be seen when Hasan first discovered the bot](https://clips.twitch.tv/ConfidentArtisticRutabagaKevinTurtle-LzPv2rHJROiM0bA_).

### Why does the bot chat normally sometimes?

The bot has some commands that are only usable by me and some friends. It used to have a command, called "$shadow", that would route whatever we're saying through the bot, without an indication that the message came from someone else. If you ever saw the bot chatting normally, it was one of us puppeteering it.

Twitch bots are also not like Discord bots - the user who created the bot's account may still login as the bot, and use the account as normal. This hasn't been done since the initial few days of the bot's deployment, however (there was one message sent in Hasan's chat, from me, that was done to test something).

### Why is the bot's name pink?

It's a small homage to a friend of mine in chat, whose name also ends in "bot" (but isn't one).

### Are my messages kept somewhere?

Temporarily, yes - they have to be. Permanently, no.

In computing, there's this concept of volatile, and non-volatile memory. Volatile memory is stuff like random-access memory (or RAM) - this is typically for things that a program may need to remember for its lifespan, but may not necessarily require it in future lifespans. Non-volatile memory is stuff like hard drives - things that a program may, still, need to remember for its lifespan, but may also require it in future lifespans.

TopOTheHourBot runs solely on *volatile* memory - it will not know anything about what it has done in the past after it's taken offline and re-booted (which is done everyday). Meaning that the bot *cannot* keep messages or other information permanently.

If a message has no relevance to the bot (i.e., it's a message that won't count towards any ongoing average), it's almost immediately discarded from memory. If a message does have relevance to the bot, the score is extracted from the message's content, and everything else is discarded except the name of the user who sent the message. The name tied to this message is used in a [set](https://en.wikipedia.org/wiki/Set_(mathematics)) (basically, a collection of unique elements) to determine who has/hasn't submitted a score. When the tallying phase has come to a close, all of the names and scores are then discarded from memory to repeat the process later.

### Why is there a minimum number of chatters needed for the bot to send out an average?

If a single chatter could trigger the bot, it would almost certainly be sending a message every few seconds due to people constantly invoking it - this is probably the biggest reason for the minimum. The other is that you may have chatters sending an emote and score pairing outside of an ad segue, likely not in as large a quantity, and so a minimum works well to prevent some false positive detections.

## Requirements

The bot was written using Python 3.10. Its only external requirement is [TwitchIO](https://twitchio.dev/en/latest/) (version 2.4.0 at the time of development).

This repository serves only as a public display of the bot's source code, and is not used by the system that hosts the bot. The bot is ran using a rudimentary scheduling script, hosted on a [Raspberry Pi](https://www.raspberrypi.com/).

## Contributing

Feel free to open pull requests and issues here. While this repository is not used by the aforementioned Raspberry Pi, I (Braedyn) can merge changes with the "official" running version.

This personal mini-project has been considered finished for a while. Though, if you have ideas for a more comprehensive segue-detection system, do consider opening a pull request and/or issue to discuss.
