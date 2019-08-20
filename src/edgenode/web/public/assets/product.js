// https://gist.github.com/cybercase/db7dde901d7070c98c48#gistcomment-2400061
function product(iterables, repeat) {
    var argv = Array.prototype.slice.call(arguments), argc = argv.length;
    if (argc === 2 && !isNaN(argv[argc - 1])) {
        var copies = [];
        for (var i = 0; i < argv[argc - 1]; i++) {
            copies.push(argv[0].slice()); // Clone
        }
        argv = copies;
    }
    return argv.reduce(function tl(accumulator, value) {
        var tmp = [];
        accumulator.forEach(function (a0) {
            value.forEach(function (a1) {
                tmp.push(a0.concat(a1));
            });
        });
        return tmp;
    }, [[]]);
}