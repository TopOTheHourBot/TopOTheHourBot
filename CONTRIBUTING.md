# Contributing

Heyyo! If you're reading this, then that means you're thinking about making a contribution - that's great!

If you're **not familiar** with programming, you can create an [issue](https://github.com/TopOTheHourBot/TopOTheHourBot/issues) to describe your idea. If I like your idea, I will develop the implementation and grant you credit in this repository's [README](./README.md). If you don't want to create a GitHub account, feel free to message me (@Lyystra) in chat - I'm typically in [Hasan](https://www.twitch.tv/hasanabi)'s, [Will](https://www.twitch.tv/willneff)'s, or [Jerma](https://www.twitch.tv/jerma985)'s.

If you're **familiar** with programming, the rest of this document is dedicated to getting you up-to-speed on how TopOTheHourBot works and where in the code to construct new features. You'll of course be given credit in the repository's [README](./README.md) if your contributions are merged.

In general, if you're thinking about making a contribution that interacts with non-privileged chatters (chatters that are not moderators, VIPs, or Hasan) in some manner, **I will be seeking approval from Hasan's moderators first**. This wasn't an explicit requirement given to me by them, but I'd very much prefer if this was done so as to ensure that the feature doesn't come into conflict with their expectations of chat.

Certain features will **always** be denied. Please do not ask about or create features that perform any of the following:

1. Persistently collects user-associated data, regardless of ephemerality.
    1. Persistence, in this context, is referring to the state of existence between sessions of execution. User-associated data may only be collected in the execution state - all collections must be discarded when the session ends.
2. Grants non-privileged chatters the ability to "spam" messages, regardless of its compliance to Twitch Terms of Service, through the TopOTheHourBot client.
    1. This is specifically referring to "deliberate spam" - a feature that is knowingly making an attempt to send messages at a fast rate. "Accidental spam" is permitted - e.g., a command, ad segue, and a roleplay moment could all occur simultaneously and trigger the client to send three messages at once.

Of course, everything from the [Twitch Developer Services Agreement](https://www.twitch.tv/p/en/legal/developer-agreement/) also applies. All code contributions will be subject to the [MIT license](./LICENSE).
