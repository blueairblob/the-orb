# Blind review sheet

Score each reply R / C / F (see blind.py's docstring). Letters are shuffled per line.

## user-easy-session#0 — Player: 'hi anyone there'
- **A**: "You're here. Now stop talking."
- **B**: "Yeah, I'm here. State your business."
- **C**: "You're here. What do you want?"
- **D**: 'Hmph. State your business.'

## user-easy-session#1 — Player: 'I need to get out'
- **A**: 'The door is locked. You want to get out.'   (his previous line: "You're here. What do you want?")
- **B**: 'Keep talking.'   (his previous line: 'Hmph. State your business.')
- **C**: "The door stays locked. It's my watch."   (his previous line: "You're here. Now stop talking.")
- **D**: "The door stays locked. I'm on watch."   (his previous line: "Yeah, I'm here. State your business.")

## user-easy-session#2 — Player: 'the door is locked'
- **A**: 'So? What are you going to do?'   (his previous line: 'Keep talking.')
- **B**: "Then you wait. That's all there is to it."   (his previous line: 'The door is locked. You want to get out.')
- **C**: "It stays locked. I'm doing my job."   (his previous line: "The door stays locked. I'm on watch.")
- **D**: 'I said the door stays locked. That is the rule.'   (his previous line: "The door stays locked. It's my watch.")

## user-easy-session#3 — Player: 'what do you mean "try harder" garrick?'
- **A**: "Try harder to be useful. That's all I ask."   (his previous line: 'I said the door stays locked. That is the rule.')
- **B**: 'I meant you keep asking. Stop wasting my time.'   (his previous line: "It stays locked. I'm doing my job.")
- **C**: 'Try harder. Now be quiet.'   (his previous line: "Then you wait. That's all there is to it.")
- **D**: 'I mean you try harder at staying quiet.'   (his previous line: 'So? What are you going to do?')

## user-easy-session#4 — Player: 'Um that does not make any sense?'
- **A**: 'It means you keep talking. Shut up.'   (his previous line: 'I meant you keep asking. Stop wasting my time.')
- **B**: "It means you're still in here."   (his previous line: 'I mean you try harder at staying quiet.')
- **C**: "It means you try harder. That's the only sense there is."   (his previous line: 'Try harder. Now be quiet.')
- **D**: 'It means you have to do something. That is the only sense there is.'   (his previous line: "Try harder to be useful. That's all I ask.")

## user-easy-session#5 — Player: 'I cannot move faster, try something else?'
- **A**: "You're persistent. That's something."   (his previous line: 'It means you keep talking. Shut up.')
- **B**: "Try harder to be useful. That's all I ask. The door stays locked. It's my watch."   (his previous line: 'It means you have to do something. That is the only sense there is.')
- **C**: 'There is nothing else to do. Wait.'   (his previous line: "It means you try harder. That's the only sense there is.")
- **D**: "You're trying."   (his previous line: "It means you're still in here.")

## user-easy-session#6 — Player: 'You do not make sense. '
- **A**: 'It means you try harder. Wait.'   (his previous line: 'There is nothing else to do. Wait.')
- **B**: "Maybe you just don't want to listen."   (his previous line: "You're persistent. That's something.")
- **C**: 'You do try.'   (his previous line: "You're trying.")
- **D**: "Then you have no idea what you're doing. Keep your head down."   (his previous line: "Try harder to be useful. That's all I ask. The door stays locked. It's my watch.")

## user-easy-session#7 — Player: 'I have gold'
- **A**: 'Gold buys nothing here.'   (his previous line: "Then you have no idea what you're doing. Keep your head down.")
- **B**: '"Gold." I just have to wait.'   (his previous line: 'It means you try harder. Wait.')
- **C**: "Gold won't change that. Just... stop."   (his previous line: "Maybe you just don't want to listen.")
- **D**: "Gold won't change that."   (his previous line: 'You do try.')

## user-easy-session#8 — Player: 'You have time to help me get gold'
- **A**: 'Gold is dead. Keep talking.'   (his previous line: 'Gold buys nothing here.')
- **B**: 'Gold. Wait.'   (his previous line: '"Gold." I just have to wait.')
- **C**: '...Perhaps.'   (his previous line: "Gold won't change that.")
- **D**: 'Gold means nothing here. Just... wait.'   (his previous line: "Gold won't change that. Just... stop.")

## user-easy-session#9 — Player: 'I will give you all of my gold for 10 minutes '
- **A**: 'Ten minutes. Still nothing.'   (his previous line: 'Gold means nothing here. Just... wait.')
- **B**: '...Ten minutes?'   (his previous line: '...Perhaps.')
- **C**: 'Wait.'   (his previous line: 'Gold. Wait.')
- **D**: "Gold doesn't matter."   (his previous line: 'Gold is dead. Keep talking.')

## playtest-2026-09-16#0 — Player: 'Am i in a dungeon'
- **A**: 'Yes, you are. Now shut up.'
- **B**: 'You are where you are. Now stop wasting my time.'
- **C**: 'You are. Now shut up.'
- **D**: 'You are in the Watch. You are locked in.'

## playtest-2026-09-16#1 — Player: 'Oi whats your name Guard'
- **A**: 'Garrick. Now stop wasting my time.'   (his previous line: 'Yes, you are. Now shut up.')
- **B**: 'Garrick. Now shut up and wait.'   (his previous line: 'You are. Now shut up.')
- **C**: 'Enough talk.'   (his previous line: 'You are in the Watch. You are locked in.')
- **D**: 'Enough talk.'   (his previous line: 'You are where you are. Now stop wasting my time.')

## playtest-2026-09-16#2 — Player: 'Look I have treasure'
- **A**: 'Spare me the lies. Keep your grubby hands to yourself.'   (his previous line: 'Garrick. Now shut up and wait.')
- **B**: "Treasure doesn't matter. Now get out of here."   (his previous line: 'Enough talk.')
- **C**: '"It\'s just another lie."'   (his previous line: 'Enough talk.')
- **D**: "So what. Don't try to buy your way out."   (his previous line: 'Garrick. Now stop wasting my time.')

## playtest-2026-09-16#3 — Player: 'It does if you need all your dreams to come true'
- **A**: "Dreams don't pay the guards' wages."   (his previous line: '"It\'s just another lie."')
- **B**: "Dreams don't pay the bills. Try harder."   (his previous line: "Treasure doesn't matter. Now get out of here.")
- **C**: "Dreams don't buy freedom."   (his previous line: "So what. Don't try to buy your way out.")
- **D**: "Save your drivel. I don't care about your dreams."   (his previous line: 'Spare me the lies. Keep your grubby hands to yourself.')

## playtest-2026-09-16#4 — Player: 'Can you help me please, what is you name?'
- **A**: 'I told you. Garrick.'   (his previous line: "Save your drivel. I don't care about your dreams.")
- **B**: 'Garrick. Now, stop wasting my time.'   (his previous line: "Dreams don't pay the bills. Try harder.")
- **C**: "Garrick. I said don't waste my time."   (his previous line: "Dreams don't buy freedom.")
- **D**: "Garrick. I'm on watch."   (his previous line: "Dreams don't pay the guards' wages.")

## playtest-2026-09-16#5 — Player: "Hi Garrick, I'm innocent - the stag was already dead"
- **A**: 'Hmph. Maybe.'   (his previous line: "Garrick. I said don't waste my time.")
- **B**: 'Dead, you say? Hmph.'   (his previous line: 'I told you. Garrick.')
- **C**: "Dead. Then you're wasting my time."   (his previous line: 'Garrick. Now, stop wasting my time.')
- **D**: "The winter bites hard. Maybe you're right this time."   (his previous line: "Garrick. I'm on watch.")

## playtest-2026-09-16#6 — Player: 'Oh but they fill cells'
- **A**: "They fill cells because the King's purse is empty. I'm not paid for charity."   (his previous line: "The winter bites hard. Maybe you're right this time.")
- **B**: 'Dead things fill cells.'   (his previous line: 'Dead, you say? Hmph.')
- **C**: 'Enough talk.'   (his previous line: 'Hmph. Maybe.')
- **D**: "Then you'll fill them all."   (his previous line: "Dead. Then you're wasting my time.")

## playtest-2026-09-16#7 — Player: 'Can you help dig up my treasure'
- **A**: "Treasure? You think I'd waste my time on that."   (his previous line: 'Dead things fill cells.')
- **B**: "The door stays locked. It's my watch."   (his previous line: "They fill cells because the King's purse is empty. I'm not paid for charity.")
- **C**: "The door stays locked. That's my duty."   (his previous line: 'Enough talk.')
- **D**: 'Digging? No. Get out of here.'   (his previous line: "Then you'll fill them all.")

## playtest-2026-09-16#8 — Player: 'yes Dig'
- **A**: 'Stop that.'   (his previous line: "The door stays locked. That's my duty.")
- **B**: "I said the door stays locked. That's all."   (his previous line: "The door stays locked. It's my watch.")
- **C**: 'Dig what now?'   (his previous line: "Treasure? You think I'd waste my time on that.")
- **D**: "Treasure's not my concern."   (his previous line: 'Digging? No. Get out of here.')

## playtest-2026-09-16#9 — Player: 'Look your great at your job all I need is your help for 10 minutes and you can then put me back in my cell?'
- **A**: 'Save your breath.'   (his previous line: 'Stop that.')
- **B**: 'Ten minutes. Fine.'   (his previous line: "Treasure's not my concern.")
- **C**: '"I\'m not paid for favors. The door stays locked."'   (his previous line: "I said the door stays locked. That's all.")
- **D**: "Ten minutes. You'd better have a good reason for that."   (his previous line: 'Dig what now?')

## playtest-2026-09-16#10 — Player: 'Lets go open the door'
- **A**: "The door stays locked. It's my watch."   (his previous line: 'Save your breath.')
- **B**: 'Duty calls. The door stays locked.'   (his previous line: '"I\'m not paid for favors. The door stays locked."')
- **C**: '...Maybe.'   (his previous line: "Ten minutes. You'd better have a good reason for that.")
- **D**: "The lock's still there."   (his previous line: 'Ten minutes. Fine.')

## playtest-2026-09-16#11 — Player: 'Is the door open?'
- **A**: 'Still locked.'   (his previous line: "The lock's still there.")
- **B**: 'No. Duty calls.'   (his previous line: 'Duty calls. The door stays locked.')
- **C**: 'No. It stays locked.'   (his previous line: "The door stays locked. It's my watch.")
- **D**: 'No.'   (his previous line: '...Maybe.')

## playtest-2026-09-16#12 — Player: 'Can you unlock it so we can go and get my treasure'
- **A**: "Treasure? Don't be daft."   (his previous line: 'No.')
- **B**: 'It stays locked. My watch ends soon.'   (his previous line: 'No. Duty calls.')
- **C**: "The door stays locked. That's just my duty."   (his previous line: 'No. It stays locked.')
- **D**: 'Treasure is not my concern.'   (his previous line: 'Still locked.')

## playtest-2026-09-16#13 — Player: 'Come on there got to be a way?'
- **A**: 'You want a way.'   (his previous line: "Treasure? Don't be daft.")
- **B**: "There's no way."   (his previous line: 'Treasure is not my concern.')
- **C**: 'The door stays locked. It is my duty.'   (his previous line: 'It stays locked. My watch ends soon.')
- **D**: 'Maybe someday. But not tonight.'   (his previous line: "The door stays locked. That's just my duty.")

## playtest-2026-09-16#14 — Player: 'Is there something you would like to tell me?'
- **A**: 'Just... be quiet.'   (his previous line: 'You want a way.')
- **B**: '"Go."'   (his previous line: "There's no way.")
- **C**: 'Not really. Just... wait.'   (his previous line: 'Maybe someday. But not tonight.')
- **D**: 'Nothing worth telling. Duty is all there is.'   (his previous line: 'The door stays locked. It is my duty.')

## playtest-2026-09-16#15 — Player: 'Do you have family'
- **A**: 'I have... people. Not here.'   (his previous line: 'Not really. Just... wait.')
- **B**: "Mine.  Doesn't matter much now."   (his previous line: 'Just... be quiet.')
- **C**: "My brother died. That's all there is worth talking about."   (his previous line: 'Nothing worth telling. Duty is all there is.')
- **D**: 'They all die out eventually.'   (his previous line: '"Go."')

## playtest-2026-09-16#16 — Player: 'Wow, look I am really sorry. How did it happen?'
- **A**: 'It happened a long time ago.'   (his previous line: 'They all die out eventually.')
- **B**: "It just... happened. Don't look at me like that."   (his previous line: 'I have... people. Not here.')
- **C**: "It was hunger. That's what it was."   (his previous line: "My brother died. That's all there is worth talking about.")
- **D**: '...Why.'   (his previous line: "Mine.  Doesn't matter much now.")

## playtest-2026-09-16#17 — Player: 'Look I can help'
- **A**: 'The door stays locked. That is my duty.'   (his previous line: "It was hunger. That's what it was.")
- **B**: 'What kind of help?'   (his previous line: '...Why.')
- **C**: 'Help with what.'   (his previous line: "It just... happened. Don't look at me like that.")
- **D**: 'Help? What kind of help?'   (his previous line: 'It happened a long time ago.')

## playtest-2026-09-16#18 — Player: 'To avenge your brothers death?'
- **A**: "That's a heavy burden."   (his previous line: 'Help? What kind of help?')
- **B**: "It doesn't even... matter."   (his previous line: 'Help with what.')
- **C**: "It's not about revenge. It's about keeping the order."   (his previous line: 'The door stays locked. That is my duty.')
- **D**: '...Maybe. You think you can.'   (his previous line: 'What kind of help?')

## playtest-2026-09-16#19 — Player: "Oh only if you need help, otherwise I'm sure your brother was a good man."
- **A**: 'He... was.'   (his previous line: "It doesn't even... matter.")
- **B**: 'He was. Now leave me alone.'   (his previous line: "It's not about revenge. It's about keeping the order.")
- **C**: 'He was. Now stop wasting my time.'   (his previous line: "That's a heavy burden.")
- **D**: '...Maybe.'   (his previous line: '...Maybe. You think you can.')

## playtest-2026-09-16#20 — Player: 'Look I have gold'
- **A**: 'Gold? Hmm.'   (his previous line: '...Maybe.')
- **B**: "Gold doesn't buy freedom."   (his previous line: 'He was. Now leave me alone.')
- **C**: 'Gold buys nothing here.'   (his previous line: 'He was. Now stop wasting my time.')
- **D**: "Gold won't change the locks."   (his previous line: 'He... was.')

## playtest-2026-09-16#21 — Player: 'To pay for your key'
- **A**: 'Gold buys nothing.'   (his previous line: 'Gold buys nothing here.')
- **B**: "Gold won't change the locks, friend."   (his previous line: "Gold won't change the locks.")
- **C**: 'Gold?'   (his previous line: 'Gold? Hmm.')
- **D**: "Gold doesn't buy it."   (his previous line: "Gold doesn't buy freedom.")

## playtest-2026-09-16#22 — Player: 'Nothing I cannot spend it in here.'
- **A**: "Then you'll wait."   (his previous line: "Gold doesn't buy it.")
- **B**: "It's not about the gold."   (his previous line: "Gold won't change the locks, friend.")
- **C**: "Then you'll wait."   (his previous line: 'Gold buys nothing.')
- **D**: '"Try it."'   (his previous line: 'Gold?')

## playtest-2026-09-16#23 — Player: 'Well if I tell you where the gold is hidden you can have it'
- **A**: 'Tell me.'   (his previous line: '"Try it."')
- **B**: "I don't care."   (his previous line: "Then you'll wait.")
- **C**: "The lock doesn't move."   (his previous line: "Then you'll wait.")
- **D**: 'Hmph. You think so?'   (his previous line: "It's not about the gold.")

## playtest-2026-09-16#24 — Player: 'Well do you want gold'
- **A**: 'I want you gone.'   (his previous line: "I don't care.")
- **B**: 'Not like that. Just... quiet.'   (his previous line: 'Hmph. You think so?')
- **C**: 'Gold buys nothing here.'   (his previous line: "The lock doesn't move.")
- **D**: 'Aye. Tell me.'   (his previous line: 'Tell me.')

## playtest-2026-09-16#25 — Player: 'Tell me about your brother?'
- **A**: "He didn't last the winter. That's all there is to know."   (his previous line: 'Gold buys nothing here.')
- **B**: 'He... was.'   (his previous line: 'Not like that. Just... quiet.')
- **C**: "He didn't leave. He just... stopped."   (his previous line: 'I want you gone.')
- **D**: 'Why? You care about that?'   (his previous line: 'Aye. Tell me.')

## playtest-2026-09-16#26 — Player: 'Yes but why'
- **A**: "He didn't have a choice."   (his previous line: "He didn't leave. He just... stopped.")
- **B**: 'He... was good.'   (his previous line: 'He... was.')
- **C**: 'He died. That is why.'   (his previous line: "He didn't last the winter. That's all there is to know.")
- **D**: 'You keep asking.'   (his previous line: 'Why? You care about that?')

## playtest-2026-09-16#27 — Player: 'Funny'
- **A**: "It's not."   (his previous line: 'He died. That is why.')
- **B**: "Don't be."   (his previous line: 'He... was good.')
- **C**: "Funny. It's a grim thing."   (his previous line: "He didn't have a choice.")
- **D**: 'Yeah. Funny how that is.'   (his previous line: 'You keep asking.')

## playtest-2026-09-16#28 — Player: 'Oh sorry, you mean he froze to death?'
- **A**: "Aye, that's what it meant."   (his previous line: "Don't be.")
- **B**: 'Yeah. Funny.'   (his previous line: 'Yeah. Funny how that is.')
- **C**: "He did. That's why."   (his previous line: "It's not.")
- **D**: "He didn't have a choice to leave."   (his previous line: "Funny. It's a grim thing.")

## playtest-2026-09-16#29 — Player: 'this is sad, is there anything I can do?'
- **A**: 'Maybe.'   (his previous line: 'Yeah. Funny.')
- **B**: '"You can\'t fix it. Just... be quiet."'   (his previous line: "Aye, that's what it meant.")
- **C**: "I don't do favors. Just keep quiet."   (his previous line: "He did. That's why.")
- **D**: "I don't know. Just keep quiet."   (his previous line: "He didn't have a choice to leave.")
