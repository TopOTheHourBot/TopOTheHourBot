# TopOTheHourBot

TopOTheHourBot is a simple Twitch IRC bot that only runs in [HasanAbi](https://www.twitch.tv/hasanabi)'s chat. Its primary function is to average ratings given by chatters when Hasan performs an ad segue.

![](./assets/header.png)

TopOTheHourBot is a partner to the [HasanHub](https://www.hasanhub.com/) project, currently being developed by [chrcit](https://github.com/chrcit). Average ratings are reported to a HasanHub database for upcoming features of the website.

## Mechanics

For TopOTheHourBot to report an average rating to the chat, two things must occur:

1. There must be at least 40 messages that contain a rating.
2. These messages must be sent within 8.5 seconds of each other.

Note that the word, "messages", was carefully chosen here - the averager **does not care** if the same chatter has contributed more than once. This means that spamming your rating **does** influence the average, but is practically imperceptible when other chatters are doing the same with their own rating.

Ratings are expected to take the form "X/10", where "X" is any number. Numbers outside of the 0-10 range are [clamped](https://en.wikipedia.org/wiki/Clamping_(graphics)). The rating can be present anywhere within the message, with only the left-most one taken into account if there are multiple. To reference a rating without contributing to the average, you can surround it with quotations.


https://github.com/TopOTheHourBot/TopOTheHourBot/assets/53410383/630a1114-019b-4e16-bbce-8c27758c630b

<p align="center"><i>TopOTheHourBot running in my chat with a minimum of 3 messages and a 5 second timeout.</i></p>

In addition to averaging segue ratings, TopOTheHourBot has recently gained the ability to total Hasan's roleplay scores (+1s and -1s). It does this in a near-identical fashion to averaging segue ratings, but instead requires just 20 messages within 8 seconds of each other - the lower message threshold being due to the lower density of chatters that watch Hasan's gaming sessions.

## FAQ

### Can I submit multiple ratings?

You can, yes. Prior iterations of the bot did not allow this, but, I ultimately decided that it'd be more fun if chatters could fight to skew the average.

### Can I submit a negative rating? A rating that's greater than 10? A decimal?

The rating's numerator can be **any** number, even numbers less than 0 or greater than 10. Numbers outside of the 0-10 range are [clamped](https://en.wikipedia.org/wiki/Clamping_(graphics)), however.

The rating can be present anywhere within your chat message. If your message contains multiple ratings, only the left-most rating is taken into account.

If you want to reference a rating but not have it contribute to the average, you can surround the rating with quotations.

### When does the bot run?

It is almost always running, even while Hasan is offline. Sometimes it'll be offline if its access has expired, or if I need to take it down for maintenance.

You can check if the bot is online by looking for its name in the viewer list, beneath the VIPs section.

### How is the bot ran?

The bot currently runs on a [DigitalOcean Droplet](https://www.digitalocean.com/products/droplets) (a virtual machine). It can be invoked from its command-line interface implemented by [main.py](./main.py) - see its module docstring for more details.

### Why did the bot not send out a message at [some moment in time]?

Either the bot was offline, or not enough chatters had contributed to the average. TopOTheHourBot used to suffer from server drops, but, Hasan had since granted it VIP status, which prevents this issue.

If you didn't already know: when a Twitch chat has a lot of users, messages get served in batches - this is why it may appear to move and stop periodically. If you don't send a message while the chat is moving, your message is "dropped" (i.e., discarded) by the Twitch servers to save on resources. Server drops [are visualized by Chatterino](https://github.com/Chatterino/chatterino2/issues/1213), but not the native Twitch web client. The native client "lies" to you by displaying your message on the screen when, in actuality, it may have never been sent.

Again, however, this issue has been nullified by Hasan's decision to make TopOTheHourBot a VIP. Users with the "Broadcaster", "Moderator", or "VIP" designation are given message priority over a standard user.

### Why does the bot not have a bot badge like Fossabot?

The bot badge is a [BetterTTV](https://betterttv.com/) designation that must be assigned by the broadcaster. I do not think it's significant enough to warrant bothering Hasan about it, and please do not do so on my behalf.

### Are my messages kept somewhere?

TopOTheHourBot runs almost entirely on ephemeral memory. Content such as messages, usernames, etc. are kept for microseconds at a time. Currently, Hasan's total roleplay score is the only piece of data kept between login sessions.

To HasanHub, TopOTheHourBot simply tells it each average rating, the time at which they were calculated, and [an ID](https://en.wikipedia.org/wiki/Universally_unique_identifier) that signifies what streaming session they're a part of.

### Is there a log of the bot's messages somewhere?

HasanHub might include a record of the bot's scores in the near future (I'm not entirely sure what chrcit intends to do with the data, other than provide visualizations), but not its chat messages.

There exists publicly-accessible logging websites, but, per [Twitch's Developer Agreement](https://www.twitch.tv/p/en/legal/developer-agreement/) (under Additional Terms, Requirements for Specific Features and APIs, Chat):

> Only retain chat logs as necessary for the operation of Your Services or to improve Your Services; **do not do so for the purpose of creating public databases**, or, in general, to collect information about Twitch’s end users.

And thus, I will not be linking any such website to avoid association - I'm additionally skeptical of the intent behind these logging websites in general.

## Requirements

TopOTheHourBot requires Python 3.12. This version of Python was primarily chosen for the improvements it provides to the [`asyncio`](https://docs.python.org/3/whatsnew/3.12.html#asyncio) module, along with the myriad of [CPython optimizations](https://docs.python.org/3/whatsnew/3.11.html#faster-cpython) that came packaged in Python 3.11.

The API that TopOTheHourBot uses was built almost entirely from scratch. To get it running, you'll need to install three libraries - two of these built specifically for this project and are not available through PyPI:
- [`ircv3`](https://github.com/TopOTheHourBot/ircv3)
- [`channels`](https://github.com/TopOTheHourBot/channels)
- [`websockets`](https://websockets.readthedocs.io/en/stable/)

The [contribution guide](./CONTRIBUTING.md) has more details.

## Contributing

TopOTheHourBot accepts contributions - there is a [contribution guide](./CONTRIBUTING.md) that provides more details.

If you ever have questions about how the bot is working in some areas, how to implement something, where things are located, etc. please feel free to create an issue and I'll get back to you ASAP!

## Auditing

TopOTheHourBot is completely open to audits as described by the [Twitch Developer Agreement](https://www.twitch.tv/p/en/legal/developer-agreement/), section IV. Developer Accounts and Rate Limits, sub-section E. Audit and Monitoring.

The code on the main branch of this repository is **not always** reflective of the code that is being executed during deployment - the deployment build is sometimes using an older state of the branch in times of change. The virtual machine that deploys the bot has a clone of the main branch that is simply fast-forwarded when the branch's state is deemed stable.

Please send a message to the email listed under [my GitHub profile](https://github.com/braedynl) if access to the virtual machine is desired.

## Credit

This bot is *not* directly associated with any other project pertaining to Hasan's ad segues unless it is also disclosed by this document.

You are entirely free to record and/or use data emitted by TopOTheHourBot without any kind of permission (for logging, analysis, etc.). Referencing TopOTheHourBot's Twitch page, or its GitHub repository, are perfectly okay as a means to provide attribution in cases where it is needed or preferred.

Bear in mind that the underlying algorithm for *how* TopOTheHourBot searches for ratings has changed a lot, and may continue to change without notice. False positives can occur (and have on many occasions) in scenarios where chatters are providing ratings for a reason unrelated to ad segues - meaning that its data is somewhat noisy. There is no method of programmatically removing this noise (no method that's easily doable, anyways).
