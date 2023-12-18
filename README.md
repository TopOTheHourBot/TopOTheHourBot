# TopOTheHourBot

TopOTheHourBot is a simple bot that only runs in HasanAbi's chat. It does one thing - that thing being to tally ad segue ratings for an average.

![](./assets/example.png)

The bot reads each incoming chat message searching for "ratings": a fraction whose denominator is 10, written vaguely like "X/10", where "X" is a number between 0 and 10. If a high density of ratings can be found within a certain timespan, TopOTheHourBot will send a notification to the channel, telling the average rating.

TopOTheHourBot is a partner to the [HasanHub](https://www.hasanhub.com/) project, currently being developed by [chrcit](https://github.com/chrcit). Average ratings are sent to a HasanHub database for upcoming features of the website.

## FAQ

### Can I submit multiple ratings?

You can, yes. In prior iterations of the bot, you were unable to do so unless you had multiple accounts, but, I ultimately decided that it'd be more fun if chatters could fight to skew the average in a certain direction.

### Can I submit a negative rating? A rating that's greater than 10? A decimal?

Ratings whose numerator is outside of the range 0 to 10 (inclusive) are ignored. Decimal values within this range are completely valid, and counted towards the average as normal.

For any nerds reading this: TopOTheHourBot conducts its search using a [regular expression](https://en.wikipedia.org/wiki/Regular_expression) ([in Python flavor](https://docs.python.org/3/library/re.html)). The exact pattern is:

```python
r"""
(?:^|\s)            # should proceed the beginning or whitespace
(
  (?:(?:\d|10)\.?)  # any integer within range 0 to 10
  |                 # or
  (?:\d?\.\d+)      # any decimal within range 0 to 9
)
\s?/\s?10           # denominator of 10
(?:$|[\s,.!?])      # should precede the end, whitespace, or some punctuation
"""
```

[You can mess around with this pattern for yourself here](https://regex101.com/r/YyFggX/2).

Example messages that would be contributing a rating towards the average:

```
10/10
5 /10
0./10
3.14159265/ 10 some trailing text
.456 / 10
some text 5.5555/10 more text
4/10 this is a lot of text 5/10
```

The *first* rating is always the one that's chosen by the bot (in cases where a message contains multiple).

### When does the bot run?

Section under construction.

### How can I tell if the bot is running?

The native Twitch chat has a viewer list that tracks all active moderators and VIPs - you can check if the bot is online by looking for its name beneath the VIPs section.

### How is the bot ran?

Section under construction.

### Why does the bot chat normally sometimes?

The bot has some commands that are only usable by me, some friends, and the moderators. If you ever see the bot chatting normally, it is one of us puppeterring it.

In the past, I've also made small changes to have it reply to some friends under particular conditions.

### Why did the bot not send out a message at [some moment in time]?

Either the bot was offline, or the rating density wasn't high enough. TopOTheHourBot used to suffer from server drops, but, Hasan had recently (at the time of writing this) granted it VIP status, which prevents this issue.

If you didn't already know: when a Twitch chat is moving quickly, messages get served in batches (this is why it may appear to move and stop periodically). If you don't send a message while the chat is moving, your message is dropped by the Twitch servers to save on resources. This "drop" [is visualized by Chatterino](https://github.com/Chatterino/chatterino2/issues/1213), but not on the native Twitch web client. The native client "lies" to you by displaying your message on the screen when, in actuality, it may have never been sent.

Again, however, this issue has been nullified by Hasan's decision to make TopOTheHourBot a VIP. Users with the "Broadcaster", "Moderator", or "VIP" designation are given message priority over a standard user.

### Why does the bot not have a bot badge like Fossabot?

The bot badge is a [BetterTTV](https://betterttv.com/) designation that must be assigned by the broadcaster. I'm not going to bother Hasan about giving a bot, that only appears every hour, a crudely designed badge (and please do not do so on my behalf).

### Are my messages kept somewhere?

TopOTheHourBot runs entirely on ephemeral memory - nothing is kept between login sessions. Content such as your messages, your username, etc. are kept for nanoseconds at a time.

To HasanHub, TopOTheHourBot simply tells it each average rating, the time at which they were calculated, and [an ID](https://en.wikipedia.org/wiki/Universally_unique_identifier) that signifies what streaming session they're a part of.

### Is there a log of the bot's messages somewhere?

HasanHub might include a record of the bot's scores in the near future (I'm not entirely sure what chrcit intends to do with the data, other than provide visualizations), but not its chat messages.

There exists publicly-accessible logging websites, but, per [Twitch's Developer Agreement](https://www.twitch.tv/p/en/legal/developer-agreement/) (under Additional Terms, Requirements for Specific Features and APIs, Chat):

> Only retain chat logs as necessary for the operation of Your Services or to improve Your Services; **do not do so for the purpose of creating public databases**, or, in general, to collect information about Twitch’s end users.

And thus, I will not be linking any such website to avoid association - I'm additionally skeptical of the intent behind these logging websites in general.

## Requirements

Section under construction.

## Contributing

Section under construction.

## Credit

This bot is *not* directly associated with any other project pertaining to Hasan's ad segues unless it is also disclosed by this document.

You are entirely free to record and/or use data emitted by TopOTheHourBot without any kind of permission (for logging, analysis, etc.). Referencing TopOTheHourBot's Twitch page, or its GitHub repository, are perfectly okay as a means to provide attribution in cases where it is needed or preferred.

Bear in mind that the underlying algorithm for *how* TopOTheHourBot searches for ratings has changed a lot, and may continue to change without notice. False positives can occur (and have on many occasions) in scenarios where chatters are providing ratings for a reason unrelated to ad segues - meaning that its data is somewhat noisy. There is no method of programmatically removing this noise (no method that's easily doable, anyways).
