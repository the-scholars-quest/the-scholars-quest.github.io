let messages = [
    'Hello.',
    'At Your Service.',
    'What Ho!',
    'Aye laddy!',
    'I\'ve got a flying machine!',
    'Many of the things we secreted away could have changed the course of history...'
    'This might sound funny, but I think I\'m looking forward to today.'
    'We are the ones who will become starlight.'
    'RiIiIiIiIiIiIiInnng...'
    'Ẓ̵̱̇̂ȧ̶͙l̸̫̻̀g̷̤̞͛̀o̷̲̍!̵͎͚͝',
    'I am Malboaz.'
    'Turn the right corner... and you can find anything. Anything.'
    'Stolen wholesale.'
    'Love your life.'
    'Don\'t swear!'
    'Thou art God.'
    'You are God.'
    'We\'re all dog fuckers and maniacs and sobbing little girls hugging mommy\'s leg while daddy gets dragged away in cuffs.'
    'One day you decide life, and the world decides death.'
    'Nobody ever thinks their destiny is to be pasted crossing the street.'
    'The classified universe is certainly not smaller, and very probably much larger than this unclassified one.'
    'The overwhelming majority of secrets do not leak to the American public.'
    'Welcome to the club.'
    'The inappropriately excluded.'
    'The only way out is through.'
    'Learning how to swim right.'
    'sudo rm -rf /*'
    'Experience is the worst teacher.  It always gives the test first and the instruction afterward.'
    'Friends come and go, but enemies accumulate.'
    'Variables won\'t; constants aren\'t.'
    'Fate ... I thought you said Freight.'
    'Health is merely the slowest possible rate at which one can die.'
    'A gleekzorp without a tornpee is like a quop without a fertsneet. Sort of.'
    'Intolerance is the last defense of the insecure.'
    'You are the only person to ever get this message.'
    'It\'s a good thing we don\'t get all the government we pay for.'
    'Day of inquiry.  You will be subpoenaed.'
    'An American citizen will cross an ocean to fight for democracy, but won\'t cross the street to vote in his own.'
    'Real Users find the one combination of bizarre input values that shuts down the system for days.'
    'Assumption is the mother of all screw-ups.'
    'Why was I born with such contemporaries?'
    'You need only reflect that one of the best ways to get yourself a reputation as a dangerous citizen these days is to go about repeating the very phrases which our founding fathers used in the struggle for independence.'
    'It\'s just a jump to the left, and then a step to the right...'
    'Government lies, and newspapers lie, but in a democracy they are different lies.'
    'If there is a possibility of several things going wrong, the one that will cause the most damage will be the one to go wrong.'
    'If you think big enough, you\'ll never have to do it.'
    'If you can read this, you\'re too close.'
    'By this time tomorrow, you\'ll be dead.'
    'We might be crazy, but we aren\'t wrong.'
    'Memento mori.'
    '...and everyone is wrong once again.'
    'All natural beauty belongs to us.'
    'You would nauseate your descendents.'
    ''




function setMsg() {
    document.getElementById("message").innerHTML = "<em><q>" + messages[Math.floor(Math.random() * messages.length)] + "</q></em>";
}