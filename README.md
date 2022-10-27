# TopOTheHourBot

TopOTheHourBot is a simple bot that only runs in Hasan's chat. It does only one thing - that thing being to tally ad segue scores for an average.

The bot reads each incoming chat message searching for two things:
1. An emote, which can be any of the following:
    - DANKIES (or some near-equivalent during holidays)
    - PogO (includes peepoPogO)
    - TomatoTime
2. A score, which is a fraction whose denominator is 10, written as X/10, where:
    - X can be any number, inclusive of decimals and negatives. If X is greater than 10, or lower than 0, it's treated as if it is 10 or 0, respectively.

The ordering of the emote and score does not matter, and the message may contain other content so long as the two things appear somewhere within the message.

When an emote and score pairing is first discovered, the bot will begin a "tallying phase". Each time a new score is found, a timer is started for it to find another (the idea being that if a viewer sees a score in chat, they might be encouraged to send one themselves - so the presence of one score may indicate that there are more to come). When this timer has fully decayed, the average is calculated and sent if there were more than a certain number of chatters that submitted scores.

During a tallying phase, using an emote (from one of the few listed above) becomes unnecessary - a message that contains a score will be counted regardless of its other content. This allows more chatters to contribute a score (knowingly or unknowingly), without sacrificing the "security" that the emote provides against false positive detections. This means there must be at least one chatter that sends an emote and score pairing before messages may contain a score alone - messages that contain a score prior to this chatter's message will not be counted towards the average.

Parts of this explanation were left intentionally vague - specifically, the timer and minimum number of chatters needed for the bot to say something. These two parameters have changed a lot, [especially after Hasan first noticed it](https://clips.twitch.tv/ConfidentArtisticRutabagaKevinTurtle-LzPv2rHJROiM0bA_), and will likely receive more changes until it's about right. On the latest update to the bot, the discovery timer defaults to 9 seconds, and the minimum number of chatters defaults to 20. Though, again, these values are likely to change with time. They may also change dynamically, as the bot has commands that allow its "moderators" (me and some friends in chat) to change them while the bot is online.

## FAQ

### Are my messages kept somewhere?

Temporarily, yes - they have to be. Permanently, no.

In computing, there's this concept of volatile, and non-volatile memory. Volatile memory is stuff like random-access memory (or RAM) - this is typically for things that a program may need to remember for its lifespan, but may not necessarily require it in future lifespans. Non-volatile memory is stuff like hard drives - things that a program may, still, need to remember for its lifespan, but may also require it in future lifespans.

TopOTheHourBot runs solely on *volatile* memory - it will not know anything about what it has done in the past after it's taken offline and re-booted (which is done everyday). Meaning that the bot *cannot* keep messages or other information permanently.

If a message has no relevance to the bot (i.e., it's a message that won't count towards any ongoing average), it's almost immediately discarded from memory. If a message does have relevance to the bot, the score is extracted from the message's content, and everything else is discarded except the name of the user who sent the message. The name tied to this message is used in a [set](https://en.wikipedia.org/wiki/Set_(mathematics)) (basically, a collection of unique elements) to determine who has/hasn't submitted a score. When the tallying phase has come to a close, all of the names and scores are then discarded from memory to repeat the process later.

### Can I submit multiple scores?

The bot will use the first score it has seen from you during a tallying phase, meaning that subsequent scores are ignored. If you wanted to submit multiple scores in an effort to skew the average, you'd need multiple accounts.

### Why is there a minimum number of chatters needed for the bot to send out an average?

If a single chatter could trigger the bot, it would almost certainly be sending a message every few seconds due to people constantly invoking it - this is probably the biggest reason for the minimum. The other is that you may have chatters sending an emote and score pairing outside of an ad segue, likely not in as large a quantity, and so a minimum works well to prevent some false positive detections.

### Who made the bot?

I go by "braedye" in Twitch chat. Feel free to say hey or ask questions!

### Why does the bot chat normally sometimes?

The bot has some commands that are only usable by me and some friends. One of those commands is "$shadow", which routes whatever we're saying through the bot. If you ever see the bot talking like a normal chatter, one of us likely used that command.

Twitch bots are also not like Discord bots - the user who created the bot's account may still login as the bot, and use the account as normal. This hasn't been done since the initial few days of the bot's deployment, however.

## Requirements

The bot was written using Python 3.10. Its only external requirement is [TwitchIO](https://twitchio.dev/en/latest/) (version 2.4.0 at the time of development).

This repository serves only as a public display of the bot's source code, and is not used by the system that hosts the bot. The bot is ran using a rudimentary scheduling script, hosted on a [Raspberry Pi](https://www.raspberrypi.org/).

## Contributing

Feel free to open pull requests and issues here. While this repository is not used by the aforementioned Raspberry Pi, I (Braedyn) can merge changes with the "official" running version.

This personal mini-project has been considered finished for a while. Though, if you have ideas for a more comprehensive segue-detection system, do consider opening a pull request and/or issue to discuss.
