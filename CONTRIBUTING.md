# Contributing

Heyyo! If you're reading this, then that means you're thinking about making a contribution - that's great!

If you're **not familiar** with programming, you can create an [issue](https://github.com/TopOTheHourBot/TopOTheHourBot/issues) to describe your idea. If I like your idea, I will develop the implementation and grant you credit in this repository's [README](./README.md). If you don't want to create a GitHub account, feel free to message me (@Lyystra) in chat - I'm typically in [Hasan's](https://www.twitch.tv/hasanabi), [Will's](https://www.twitch.tv/willneff), or [Jerma's](https://www.twitch.tv/jerma985).

If you're **familiar** with programming, the rest of this document is dedicated to getting you up-to-speed on how TopOTheHourBot works and where in the code to construct new features. You'll of course be given credit in the repository's [README](./README.md) if your contributions are merged.

## Agreements

In general, if you're thinking about making a contribution that interacts with non-privileged chatters (chatters that are not moderators, VIPs, or Hasan) in some manner, **I will be seeking approval from Hasan's moderators first**. This wasn't an explicit requirement given to me by them, but I'd very much prefer if this was done so as to ensure the feature doesn't come into conflict with their expectations of chat.

Certain features will **always** be denied even though they do not necessarily violate [Twitch's Developer Agreement](https://www.twitch.tv/p/en/legal/developer-agreement/) - these are my own rules on what is and is not allowed. Please do not ask for or create features that perform the following operations:

1. Persistently collects user-associated data, regardless of ephemerality.
    1. Persistence is referring to the state of existence between sessions of execution. User-associated data may only be collected in the execution state - all collections must be discarded when the session ends.
    2. This includes basic collection of user names, even if they are not mapped to pieces of data. The collection itself holds meaning.
    3. Persistent collection of user-associated data is only permitted if the user, themself, encoded user-associated data within an otherwise non-user-associated storage interface.
        1. An example of this would be a command that logs its arguments to a local file, where the user has invoked the command with user-associated data as argument(s).
        2. If such a circumstance is possible, it should be stated in the interface.
2. Grants non-privileged chatters the ability to spam messages, regardless of its compliance to Twitch Terms of Service, through the TopOTheHourBot client.
    1. This is specifically referring to "deliberate spam" - a feature that is knowingly making an attempt to send messages at an abnormally fast rate. "Accidental spam" is permitted - e.g., a command, ad segue, and a roleplay moment could all occur simultaneously and trigger the client to send three messages at once - the individual components did not attempt to spam, themselves, and so it is permissible.
    2. There is no concrete definition of "spam". In general, I consider it to be any routine that sends a lot of messages in a short timeframe - it is an "I know it when I see it" kind of thing, and so the wording with regards to this rule is deliberately vague.

TopOTheHourBot is, and will always be open source. All code contributions will be subject to the [MIT license](./LICENSE).

## Getting Started

TopOTheHourBot is written in Python 3.12. Twitch chats, and especially Hasan's chat, can be extremely fast and so you might wonder why Python was the language of choice. There isn't really a satisfying answer to that, other than I just know Python better than any other language, and it's more than capable to handle the speed of Hasan's chat. Python can certainly be slow, but recent versions of the language have made great strides to speed it up. Keep in mind that a vast majority of chat messages are single words - often, emotes (e.g., KEKW, FeelsStrongMan, Bedge) - and so processing messages takes a lot less time than you might think.

TopOTheHourBot uses an API that was built almost entirely from scratch. For a long time, the bot was implemented using [TwitchIO](https://twitchio.dev/en/stable/), but I slowly became annoyed with its callback-dependent nature and tendency to have connection issues. There are three libraries that comprise TopOTheHourBot's API, two of which were built specifically for TopOTheHourBot and are not available through PyPI (installation instructions are in their respective READMEs):
- [`ircv3`](https://github.com/TopOTheHourBot/ircv3)
- [`channels`](https://github.com/TopOTheHourBot/channels)
- [`websockets`](https://websockets.readthedocs.io/en/stable/)

My personal development setup uses [Visual Studio Code](https://code.visualstudio.com/) with [Pylance](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance) (using the `"basic"` type-checking option). TopOTheHourBot provides [a CLI](./main.py) that I recommend using in a debug configuration (your local .vscode/launch.json file):

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "TopOTheHourBot",
            "type": "python",
            "request": "launch",
            "program": "main.py",
            "args": [YOUR_TWITCH_OAUTH_TOKEN_HERE],
            "console": "integratedTerminal",
            "justMyCode": true
        }
    ]
}
```

You'll of course need a Twitch OAuth token to have this run successfully. See the [Twitch Developers documentation](https://dev.twitch.tv/docs/irc/authenticate-bot/) for details on generating one. To execute TopOTheHourBot's code under a different client, you'll want to change the `name` attribute at the top of the `TopOTheHourBot` class definition to the name of your bot's client. Likewise, to run the `HasanAbiExtension` in a different channel, you'll want to change the `target` attribute at the top of its definition to the name of the channel you'd like to have it execute in (bear in mind that the leading `#` character is necessary).

You might also want to consider changing the logging level in [main.py](./main.py) from `INFO` to `DEBUG`. Doing so will write all input and output to the log - see the [websockets documentation](https://websockets.readthedocs.io/en/stable/topics/logging.html) for more details.

## Where Are The Callbacks?

One of the first things you'll probably notice upon seeing TopOTheHourBot's code is the lack of `on_message()`, `on_connect()`, `on_whatever()` functions that are prevalent in many IRC libraries today. TopOTheHourBot is a bit quirky, in that, its most fundamental operation of averaging batch segue ratings requires two things that are awkward to implement in traditional callback-based paradigms:

1. Averaging numbers across messages requires memory of those numbers, meaning that a state must be saved across invocations to the message callback.
2. Reporting the average is based on a factor of time, meaning that the callback must have knowledge over when it has last been invoked.

TopOTheHourBot has its own paradigm that makes an attempt to address these issues. The API it uses is built on the concept of attaching and detaching buffers (called `Channel`s) to a central object. This object fans messages out to each buffer, while the buffer provides tools to handle filtering, mapping, timeouts, etc. such that states and time between a cluster of messages can be managed within a single function.

Suppose that our goal is to count the number of messages that contain the string `"hello"` - in a callback-based framework, this count must exist in the outer scope to "remember" what the prior count was:

```python
class Listener:

    def __init__(self) -> None:
        self.hello_count = 0

    async def on_message(self, message: Message) -> None:
        if "hello" in message.content:
            self.hello_count += 1
```

Under the TopOTheHourBot paradigm, this count can be restricted to the scope of a single function, allowing us to avoid cluttering the outer scope:

```python
class Listener:

    def __init__(self) -> None:
        ...

    async def hello_counter(self) -> int:
        with self.attachment() as channel:
            hello_count = await (
                aiter(channel)
                    .map(lambda message: message.content)
                    .filter(lambda content: "hello" in content)
                    .count()
            )
        return hello_count
```

While not particularly egregious, imagine a scenario where you have a multitude of variables that need to be defined in a similar fashion - each having to exist in the outer scope while potentially serving vastly different purposes - and you'll probably see the reason why TopOTheHourBot does things so differently (it just becomes a mess).

## Architecture

With all of that said, let's finally take a look at how the TopOTheHourBot implementation uses this concept to full effect.

You can really think of TopOTheHourBot as being a large [fan-out/fan-in](https://en.wikipedia.org/wiki/Fan-out_(software)) system. In the code, there is a `TopOTheHourBot` client class, and a `HasanAbiExtension` "client extension" class. `TopOTheHourBot`, by itself, does not do much at all - its sole job is to respond to [PINGs](https://modern.ircdocs.horse/#ping-message), and distribute incoming commands to its attachments. `HasanAbiExtension` is where much of the actual work is being done. While seemingly unnecessary, this apportioning of Hasan-specific operations was done in case the bot ever obtains capabilities in other channels - it's a future-proofing measure. The diagram, below, shows the flow of messages from the underlying websocket connection to this system:[^1]

```mermaid
stateDiagram-v2
    state WebSocketClientProtocol {
        direction LR
        [*] --> TopOTheHourBot
        TopOTheHourBot --> [*]
        state TopOTheHourBot {
            direction LR
            [*] --> TopOTheHourBot.distribute()
            TopOTheHourBot.distribute() --> TopOTheHourBot.accumulate()
            TopOTheHourBot.distribute() --> HasanAbiExtension
            TopOTheHourBot.accumulate() --> [*]
            HasanAbiExtension --> [*]
            state HasanAbiExtension {
                direction LR
                [*] --> HasanAbiExtension.distribute()
                HasanAbiExtension.distribute() --> HasanAbiExtension.handle_commands()
                HasanAbiExtension.distribute() --> HasanAbiExtension.handle_segue_ratings()
                HasanAbiExtension.distribute() --> HasanAbiExtension.handle_roleplay_ratings()
                HasanAbiExtension.handle_commands() --> HasanAbiExtension.accumulate()
                HasanAbiExtension.handle_segue_ratings() --> HasanAbiExtension.accumulate()
                HasanAbiExtension.handle_roleplay_ratings() --> HasanAbiExtension.accumulate()
                HasanAbiExtension.accumulate() --> [*]
            }
        }
    }
```

`TopOTheHourBot` does not, by itself, house any responsive functionality other than to reply to PINGs, as stated prior. This is done in its `accumulate()` method, and thus does not have `handle_*()` methods alike `HasanAbiExtension`.

`HasanAbiExtension` gets a bit more involved - its `distribute()` method attaches a channel to `TopOTheHourBot` on startup, and filters for Hasan-localised commands. These commands are then served to `handle_commands()`, `handle_segue_ratings()`, and `handle_roleplay_ratings()` which all are fairly self-explanatory. Each of these `handle_*()` methods attach a channel to the `HasanAbiExtension` instance and independently read incoming messages for their own purpose - `handle_commands()` responds to traditional call-and-respond commands[^2], `handle_segue_ratings()` searches and averages ad segue ratings, and `handle_roleplay_ratings()` searches and summarises roleplay ratings. These message handlers are asynchronous iterators that yield coroutines - `accumulate()` runs each of them together and dispatches these coroutines as they are yielded.

## Building a Feature

Okay, so hopefully this high-level overview has made some kind of sense - I'll now be getting into the actual code. Instead of just showing you existing code and talking about it, I think it'd be best to develop an example feature and talk about what I'm doing as I progress. It's likely that you'll want to contribute a feature that is a part of the `HasanAbiExtension`, and so we'll do something there (just not running it in Hasan's chat, though).

The feature we'll be creating is something that's difficult to replicate in a callback-based paradigm, but made incredibly easy in TopOTheHourBot's - that being a "conversational" routine, where the client sends a message and expects another message in return.

We'll have it work like this:
1. If a chatter types "topothehourbot is cringe", the client will say to the chatter to take it back.
2. The client will await the chatter's next message with a timeout, and respond accordingly based on the message's content (or, lack thereof if a timeout occurs).

https://github.com/TopOTheHourBot/TopOTheHourBot/assets/53410383/110eef17-d29a-468e-8377-f9b4a19a1b13

### Before Building

Before you begin modifying the `HasanAbiExtension`, or any other extension type for that matter, **I would first change the `target` attribute at the top of the definition to be a different chat room, such as your own**. It's a lot easier to test that way, and avoids disrupting larger chat rooms.

### Placement

When considering a new feature, think about where it would best be placed under TopOTheHourBot's architecture. For this example, it'd likely be easiest to construct a new `handle_something()` function because a state (the chatter who initially called TopOTheHourBot cringe) needs to be referenced to detect a follow-up message.

In general, any operation that deals in "cross-message" state will likely require an independent handling function. Traditional call-and-respond commands are a bit strange in TopOTheHourBot's world because they don't require later messages to be referenced - when a command is invoked, a response is dispatched and nothing more is expected - `handle_commands()` is extraordinarily different from the other handling functions because of this.

### Starting Off

We'll start off with what is essentially boilerplate for all handler functions. We'll call our function `handle_haters()`:

```python
@stream.compose
async def handle_haters(self) -> AsyncIterator[Coroutine]:
    with self.attachment() as channel:
        ...
```

`stream.compose()` is a decorator function that simply converts an asynchronous iterator or generator return into a [`Stream`](https://github.com/TopOTheHourBot/channels/blob/main/channels/stream.py). This is atop all handler functions for use by `accumulate()`, which uses the `Stream.merge()` method to collect and dispatch coroutines yielded by the handlers.

The `with self.attachment() as channel:` statement will create, attach, and ensure the detachment of a [`Channel`](https://github.com/TopOTheHourBot/channels/blob/main/channels/channel.py) instance connected to the `HasanAbiExtension`'s [`Diverter`](https://github.com/TopOTheHourBot/channels/blob/main/channels/diverter.py)[^3]. The `Diverter` is what manages the "spread" of commands and closure to each handling function - the `attachment()` method of the `HasanAbiExtension` is really just a call to `Diverter.attachment()`.

### Querying the Haters

The next step that we'll take is to search for chatters that are saying TopOTheHourBot is cringe. We want the conversation to be repeatable, and so we'll query for the infringing remark in a loop:

```python
@stream.compose
async def handle_haters(self) -> AsyncIterator[Coroutine]:
    with self.attachment() as channel:
        while (
            message := await aiter(channel)
                .filter(twitch.is_server_private_message)
                .filter(lambda message: "topothehourbot is cringe" in message.comment)
                .first()
        ):
            hater = message.sender
```

One of the first things that many handling functions do is filter the channel for private messsages, as the channel may contain other commands. [PRIVMSG](https://modern.ircdocs.horse/#privmsg-message) commands, as they're called for some reason, are simply normal chat messages.

The `Stream.first()` method being applied, here, obtains the first possible value from the filtered stream. If the stream is empty, then that can only mean the connection has been closed, and so it is okay to break our while loop by letting `Stream.first()` return `None`. Once obtaining a message with our criteria, we can save the chatter (the `message.sender`) as a state for later reference.

### Our First Message

At this point, we've obtained a message with the infringing remark, and so now we must respond. The `ClientExtension` type that `HasanAbiExtension` derives from defines a coroutine method, `message()`, to send PRIVMSG commands to the IRC server:

```python
...

await self.message(
    "D: take that back, right now !!!!!!",
    target=message,
    important=True,
)

following_message = await (
    aiter(channel)
        .filter(twitch.is_server_private_message)
        .filter(lambda message: message.sender == hater)
        .timeout(10, first=True)
        .first()
)
```

`message()` takes in two arguments aside from the message's content:
- `target` can either be a `ServerPrivateMessage` or `str`, interpreted as being a reply if a `ServerPrivateMessage`, or standard message being sent to a room if a `str`.
- `important` is a `bool` indicating whether to wait or discard the message if sending during a cooldown period. The `Client` type that `TopOTheHourBot` derives from is built such that all PRIVMSGs are subject to a 1.5 second cooldown as a means to cooperate with [Twitch rate limits](https://dev.twitch.tv/docs/irc/#rate-limits).

Note that I'm `await`ing the `message()` call as opposed to yielding it like other message handlers typically do. Since this message handler will ultimately be hooked up to the `accumulate()` method, yielding a coroutine has the effect of submitting it for the next available time slot in the [event loop](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio-event-loop) - while unlikely, it's possible that this could be a much later moment in time, so we can instead `await` the call to ensure the initial response gets out before we begin searching for a follow-up message.

After sending out our initial response, we can await the infringing user's next message by querying the `channel` again. We use the `Stream.timeout()` method to await this follow-up message for 10 seconds at maximum, and pass `first=True` to apply the timeout on first iteration[^4].

### Following the Follow-Up

To wrap things up, we must now respond to the follow-up we may or may not receive from the infringing user. There are four cases to deal with:

```python
...

if following_message is None:  # Timeout occurred
    yield self.message(
        ":z silence, huh ?",
        target=message,
        important=True,
    )
elif "no" in following_message.comment:
    yield self.message(
        "D: wtf !!!!!!!!!",
        target=following_message,
        important=True,
    )
elif "ok" in following_message.comment:
    yield self.message(
        ":D yay !!!!!!!!!",
        target=following_message,
        important=True,
    )
else:
    yield self.message(
        ":z ignoring me, huh ?",
        target=following_message,
        important=True,
    )
```

Hopefully this is fairly self-explanatory. If a timeout occurred, we'll target the original infringing message, while other cases will target the follow-up message. Obviously these response conditions are not very robust (`"no"` could be found in the word `"nothing"`, for example, which wouldn't necessarily mean that the user replied to TopOTheHourBot), but this is just for demonstration purposes - you can probably imagine much greater possibilities with this system. Unlike the initial message, I'm opting to yield these because we have no more follow-ups to go through - the event loop can send it whenever it gets a chance to.

Be sure to add new handling functions to `accumulate()`'s logic to have the routine executed:

```python
async def accumulate(self) -> None:
    ...
    async with TaskGroup() as tasks:
        async for coro in (
            self.handle_commands()
                .merge(
                    self.handle_segue_ratings(),
                    self.handle_roleplay_ratings(),
                    self.handle_haters(),  # Simply extend the call like so
                )
        ):
            tasks.create_task(coro)
```

### Full Source Code

Here is the code we wrote in totality - fairly straightforward!

```python
@stream.compose
async def handle_haters(self) -> AsyncIterator[Coroutine]:
    with self.attachment() as channel:
        while (
            message := await aiter(channel)
                .filter(twitch.is_server_private_message)
                .filter(lambda message: "topothehourbot is cringe" in message.comment)
                .first()
        ):
            hater = message.sender

            await self.message(
                "D: take that back, right now !!!!!!",
                target=message,
                important=True,
            )

            following_message = await (
                aiter(channel)
                    .filter(twitch.is_server_private_message)
                    .filter(lambda message: message.sender == hater)
                    .timeout(10, first=True)
                    .first()
            )

            if following_message is None:
                yield self.message(
                    ":z silence, huh ?",
                    target=message,
                    important=True,
                )
            elif "no" in following_message.comment:
                yield self.message(
                    "D: wtf !!!!!!!!!",
                    target=following_message,
                    important=True,
                )
            elif "ok" in following_message.comment:
                yield self.message(
                    ":D yay !!!!!!!!!",
                    target=following_message,
                    important=True,
                )
            else:
                yield self.message(
                    ":z ignoring me, huh ?",
                    target=message,
                    important=True,
                )
```

Hopefully this brief walkthrough was helpful and gives you some ideas of what more could be done with such a lenient framework. If you have any questions about the bot's code - what it's doing in certain places, how to implement something, etc. - please feel free to create an [issue](https://github.com/TopOTheHourBot/TopOTheHourBot/issues) and I'll get back to you as soon as possible!

For more information, I recommend reading through the function and class docstrings, as they should (hopefully) provide a bit more insight in areas that I've glossed over. The implementation of everything in the API was also made to be readable - seeing the logic behind the functions I've used here might be helpful as well.

Do note that contributions to TopOTheHourBot are inclusive of the other two custom libraries it uses ([`ircv3`](https://github.com/TopOTheHourBot/ircv3) and [`channels`](https://github.com/TopOTheHourBot/channels)). `ircv3` does not have an object representation of all of the valid Twitch commands, as you might've noticed, and that's simply because I didn't have a need for them just yet. If your feature requires some of these commands, feel free to expand `ircv3` as well.

## Limitations

TopOTheHourBot's API is not fully featured by any means. Certain functionality is not implemented either because I haven't found a way to implement it just yet, or because I just haven't seen it as necessary for right now:

- `HasanAbiExtension` does not account for different [chat modes](https://safety.twitch.tv/s/article/Chat-Tools?language=en_US#9ChatModes). The facilitating command for chat modes, [ROOMSTATE](https://dev.twitch.tv/docs/irc/commands/#roomstate), is interpreted by the parser but not used at the moment.
    - Hasan's chat rarely ever changes modes and so I didn't feel this was pertinent enough to implement yet.
- TopOTheHourBot does not know its own user data aside from its IRC name - its colour, display name, ID, etc. are not directly accessible through the API.
    - As to how this should be presented in the API is not something I'm aware of just yet. I have also not seen a need for it.
- TopOTheHourBot cannot read certain messages such as ban events, subscriptions, cheers, and other Twitch-specific data.
    - This is simply because a model has not been made for them in [`ircv3`](https://github.com/TopOTheHourBot/ircv3). I have not seen a need for these types of messages just yet, and so the parser does not interpret them.

Feel free to solve some of these limitations if you're up for it!

[^1]: Bear in mind that this diagram purely shows the flow of messages and not the relationship between classes. It may appear as if `TopOTheHourBot` composites `HasanAbiExtension`, for example, but it's actually the complete opposite - `HasanAbiExtension` composites `TopOTheHourBot`, and `TopOTheHourBot` composites `WebSocketClientProtocol`.

[^2]: Messages that invoke the client's command interface - typically implemented by pairing an identifying prefix to a command name (e.g., `#scramble` to begin a scramble game with BlammoBot). TopOTheHourBot uses the dollar sign, `$`, as its command prefix (chosen because of its association with ads - fun fact). `!` is used by Fossabot and `#` is used by BlammoBot.

[^3]: When `HasanAbiExtension.distribute()` is executed, commands from the IRC server are distributed through the diverter as they arrive. If the connection ever ceases, the diverter is closed and all channels that were attached cease iteration. Under most circumstances, the diverter will detach the channels by itself, causing the `attachment()` context managers to essentially take no action upon exit. One might say that its "true" purpose is in dealing with coroutines that exit prematurely, but I have not yet found a situation where a premature exit is warranted. Regardless, I advise using `attachment()` to construct and attach new channels when necessary.

[^4]: `first=False` by default because it's often that you'd want to await the sender to begin sending before the timeout goes into effect. `handle_segue_ratings()` is a good example of this - the first rating of a batch can take an unknown amount of time to discover, but ratings that follow need to be discovered within the time constraint.
