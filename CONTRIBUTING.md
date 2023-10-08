# Contributing

If you're reading this, then that means you're thinking about making a contribution to TopOTheHourBot - that's great!

If you **are not** familiar with Python and/or programming in general, you can still help! Please describe your idea as an [issue](https://github.com/TopOTheHourBot/TopOTheHourBot/issues) on this repository in as much detail as possible. If I think your idea is good, I will respond to your issue and develop the implementation. If you don't want to create a GitHub account, feel free to message me (@Lyystra) in chat - I'm typically in Hasan's or Jerma's. Do note that my whispers are *disabled*.

If you **are** familiar with Python and/or programming in general, the rest of this document is dedicated to getting you up-to-speed on how the bot operates and how/where to make additional features. TopOTheHourBot *does not* use a traditional Twitch IRC framework like [TwitchIO](https://twitchio.dev/en/stable/). It is a custom-made, low-level, asynchronous system of queues that feed into one another via [map](https://en.wikipedia.org/wiki/Map_(higher-order_function)), [filter](https://en.wikipedia.org/wiki/Filter_(higher-order_function)), and/or [reduce](https://en.wikipedia.org/wiki/Fold_(higher-order_function)) procedures. It is built on top of the wonderful [websockets](https://github.com/python-websockets/websockets) library - everything else within the framework has been constructed from the ground up.

## Why?

So why create an entirely new framework for TopOTheHourBot?

The fundamental operation of TopOTheHourBot (averaging segue ratings) that I first conceptualized when starting this project is a time-based, Hasan-specific procedure. The bot was first built with TwitchIO at its conception, but if you've worked with TwitchIO before, you know that it is a callback-based framework - meaning that, for every incoming message, a function is called with a message as an argument, and your job is then to map the message to something as a response. These messages are channel-agnostic - your callback will receive messages for *all* channels that the bot has joined, which of course necessitates a filter if you only want messages from one or a few specific channels.

Callbacks are a very difficult thing to work around when you need to have state transferring from prior invocations - something that is expressly required for averaging segue ratings. You can, of course, put your state into a class as a means to transfer data between callbacks, but I would argue that the code becomes much harder to understand in doing so. Creating a queue-based system *from* the callback system can work, but it's a massive anti-pattern - the internal system could just feed the messages directly to the queue and not have to go through the callback.

This is the very long-winded answer as to why I felt the need to design a new framework. This is not to say that callback frameworks are "bad" in any way, shape or form - it's simply that TopOTheHourBot often has to do things that don't cooperate well with a callback framework.

Now that that's out of the way, let's dive deeper into this new framework I've been speaking so much about - its design, benefits, and limitations.

## Architecture Overview

This overview assumes you are familiar with [Twitch's IRC interface](https://dev.twitch.tv/docs/irc/), and the [IRCv3 specification](https://ircv3.net/irc/).

You can think of TopOTheHourBot as being a system of pipes that feed into one another. And, when I say "pipes", I quite literally mean pipes - there is a protocol type named `Pipe`, whose definition looks like this:

```python
class Pipe(Protocol):

    @abstractmethod
    def __call__(
        self,
        isstream: SupportsRecv[IRCv3CommandProtocol],
        omstream: SupportsSend[IRCv3CommandProtocol | str],
        osstream: SupportsSend[IRCv3CommandProtocol | str],
        /,
    ) -> Coroutine:
        raise NotImplementedError
```

These arguments are:

1. `isstream` - **Input System Stream**
    - Incoming IRCv3 commands from the Twitch IRC server, including PRIVMSG commands.
2. `omstream` - **Output Message Stream**
    - Outgoing PRIVMSG commands. Other IRCv3 commands may be sent to this stream, but are subjected to certain rate limits. This stream is *latent*, meaning that some outgoing messages may be discarded if there are too many in its queue.
3. `osstream` - **Output System Stream**
    - Outgoing non-PRIVMSG IRCv3 commands. This stream accepts PRIVMSG commands, but they should *not* be sent here - use `omstream` instead. This stream is meant for commands that are not subject to rate limits, such as PONG or PART.
