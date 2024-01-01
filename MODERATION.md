# Moderation

**Note: This document is still under construction!**

This document is intended for moderators that have TopOTheHourBot running in their chat room (which is just Hasan's chat at the moment).

TopOTheHourBot does not have much with regards to functionality, as its primary purpose has been to average segue ratings. Traditional "!verb" commands, like those implemented by [Fossabot](https://fossabot.com/) and [Nightbot](https://nightbot.tv/), are actually a bit strange to TopOTheHourBot because its infrastructure was built to prioritise cross-message relationships over messages in isolation (many-to-one or many-to-many versus one-to-one).

Still, though, if you would like functionality to be added, whether that be a new command or cross-message routine, feel free to reach out - you can catch me (@Lyystra) in Hasan's, Will's, or Jerma's chat usually, or you can leave me a message in my own chat room.

## Command Syntax

This document uses a basic syntax structure to notate the arguments of a command. This structure is as follows:

- Angled brackets surrounding a name, like `<this>`, are used to notate an argument - that is, something you can provide to the command as a means for adjusting what it does. Arguments are separated from each other by one space.
  - The name is there to roughly describe what the argument's purpose is. This can of course vary from command to command.
  - Arguments may have restrictions on what possible values can be passed into it. Argument restrictions will be explained in the command's section of this document if they exist.
- An asterisk following an argument, like `<this>*`, indicates that the argument can be provided 0 or more times.
- An addition operator following an argument, like `<this>+`, indicates that the argument can be provided 1 or more times.
- A pipe nested between names or arguments, like `$this|that` or `<this|that>`, indicates that the command or argument may be invoked by alternative names or arguments.

### Examples

#### Move Once

Syntax: `$move <direction>`

Possible invocations might be:

```
$move up
$move down
$move left
$move right
```

#### Move Multiple Times

Syntax: `$move <direction>+`

Possible invocations might be:

```
$move up down
$move left right up down left
$move down
```

A value for the `<direction>` argument can now be passed in one or more times, as indicated by the `+`.

#### Move?

Syntax: `$move|walk <direction>*`

Possible invocations might be:

```
$move up down
$walk up
$move left left down up right
$walk
$move
```

`<direction>` can now be passed 0 or more times, as indicated by the `*`. It now also has an alternative name, `walk`, that can be used over `move`.

## HasanAbi's Commands

### Access

As of right now, commands are set to only be accessible by moderators, Hasan, and the following users ("proxy moderators"):

```
lyystra     # Me
astryyl     # My alt
bytesized_  # Friend of mine
emjaye      # Friend of mine
```

You cannot add proxy moderators without modifying the code at the moment. If you'd like someone to be added, contact me and I can reload the bot to include them.

### Commands

#### Ping

Syntax: `$ping`

Returns TopOTheHourBot's most recent [latency](https://en.wikipedia.org/wiki/Latency_(engineering)) measurement, in milliseconds. Latency is measured every 20 seconds or so. Upon establishing a connection to the Twitch server, the latency will be 0ms.

This command is intended mostly to determine whether the bot is online or not.

#### Copy

Syntax: `$copy|echo|shadow <word>*`

Returns the proceeding words as a message from TopOTheHourBot.

#### Code

Syntax: `$code <handle>*`

Returns a link to [TopOTheHourBot's GitHub profile](https://github.com/TopOTheHourBot), optionally mentioning the user handles that follow.

#### Roleplay Rating Total

Syntax: `$roleplay_rating_total <handle>*`

Returns Hasan's current accrual of roleplay ratings (+1s/-1s) since December 17, 2023, optionally mentioning the user handles that follow.
