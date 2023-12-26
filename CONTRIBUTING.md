# Contributing

Heyyo! If you're reading this, then that means you're thinking about making a contribution - that's great!

If you're **not familiar** with programming, you can create an [issue](https://github.com/TopOTheHourBot/TopOTheHourBot/issues) to describe your idea. If I like your idea, I will develop the implementation and grant you credit in this repository's [README](./README.md). If you don't want to create a GitHub account, feel free to message me (@Lyystra) in chat - I'm typically in [Hasan](https://www.twitch.tv/hasanabi)'s, [Will](https://www.twitch.tv/willneff)'s, or [Jerma](https://www.twitch.tv/jerma985)'s.

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

You can really think of TopOTheHourBot as being a large [fan-out/fan-in](https://en.wikipedia.org/wiki/Fan-out_(software)) system. In the code, there is a `TopOTheHourBot` client class, and a `HasanAbiExtension` "client extension" class. `TopOTheHourBot`, by itself, does not do much at all - its sole job is to respond to [PINGs](https://modern.ircdocs.horse/#ping-message), and distribute incoming commands to its attachments. `HasanAbiExtension` is where much of the actual work is being done. While seemingly unnecessary, this apportioning of Hasan-specific operations was done in case the bot ever obtains capabilities in other channels - it's a future-proofing measure. The diagram, below, shows the flow of messages from the underlying websocket connection to this system:

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

Bear in mind that this diagram purely shows the flow of messages and not the relationship between classes. It may appear as if `TopOTheHourBot` composites `HasanAbiExtension`, for example, but it's actually the complete opposite - `HasanAbiExtension` composites `TopOTheHourBot`, and `TopOTheHourBot` composites `WebSocketClientProtocol`.
