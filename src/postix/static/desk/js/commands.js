var commands = {

    _info_view: function (content) {
        $("#info-view .content").html(content);
        $("#info-view").show();
    },

    '/help': function (args) {
        commands._info_view("<p><strong>" + gettext("Supported commands:") + "</strong></p>"
            + "<dl class='dl-horizontal'>"
            + "<dt>/scanner</dt><dd>" + gettext("Show reset codes for the barcode scanner") + "</dd>"
            + "<dt>/ping</dt><dd>" + gettext("Initiate a ping") + "</dd>"
            + "<dt>/ping abcde</dt><dd>" + gettext("Save a response to a ping") + "</dd>"
            + "</dl>");
    },

    '/sell': function (args) {
        if (args[1]) {
            transaction.add_product(parseInt(args[1]));
        } else {
            var val = "<p><strong>" + gettext("Supported commands:") + "</strong></p>"
                + "<ul>";
            for (var key in productlist.products_all) {
                val += "<li><strong>/sell " + key + "</strong>: "+ productlist.products_all[key].name +"</li>"
            }
            val += "</ul>";
            commands._info_view(val);
        }
    },

    '/supply': function (args) {
        $.ajax({
            url: '/api/cashdesk/supply/',
            method: 'POST',
            dataType: 'json',
            data: JSON.stringify({
                'identifier': args.join(' ')
            }),
            headers: {
                'Content-Type': 'application/json'
            },
            success: function (data, status, xhr) {
                if (data.success === true) {
                    dialog.flash_success(gettext('Yay, you\'ve got more things now!'));
                } else {
                    dialog.show_error(data.message);
                }
            }
        });
    },

    '/ping': function(args) {
        if (args && args.length > 1) {
            $.ajax({
                url: '/api/cashdesk/pong/',
                method: 'POST',
                dataType: 'json',
                data: JSON.stringify({
                    'pong': args.join(' ')
                }),
                headers: {
                    'Content-Type': 'application/json'
                },
                success: function (data, status, xhr) {
                    dialog.flash_success(gettext('Pong. Thanks!'));
                }
            });
        } else {
            $.ajax({
                url: '/api/cashdesk/print-ping/',
                method: 'POST',
                dataType: 'json',
                data: '',
                headers: {
                    'Content-Type': 'application/json'
                },
                success: function (data, status, xhr) {
                    dialog.flash_success(gettext('Ping printed!'));
                }
            });
        }
    },

    '/scanner': function (args) {
        commands._info_view("<p><strong>" + gettext("Scan the following, in order:") + "</strong></p>"
            + "<p>"
            + "<img src='/static/postix/desk/img/scanner/honeywell01.png'>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            + "<img src='/static/postix/desk/img/scanner/honeywell02.png'>"
            + "</p>"
            + "<p>"
            + "<img src='/static/postix/desk/img/scanner/honeywell03.png'>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            + "<img src='/static/postix/desk/img/scanner/honeywell04.png'>"
            + "</p>"
            + "<p>"
            + "<img src='/static/postix/desk/img/scanner/honeywell05.png'>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            + "<img src='/static/postix/desk/img/scanner/honeywell06.png'>"
            + "</p>"
            + "<p>"
            + "<img src='/static/postix/desk/img/scanner/honeywell07.png'>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            + "<img src='/static/postix/desk/img/scanner/honeywell08.png'>"
            + "</p>");
    },

    '/arcade': function (args) {
        commands._info_view("<p><strong>" + gettext("Supported games:") + "</strong></p>"
            + "<dl class='dl-horizontal'>"
            + "<dt>/snake</dt>"
            + "<dt>/tetris</dt>"
            + "<dt>/frogger</dt>"
            + "<dt>/lightcycles</dt>"
            + "</dl>");
    },
    '/snake': function (args) {
        commands._info_view("<div style='background-color:#FFFFFF;width:500px; height:450px; margin:auto;'>"
            + "    <canvas id='the-game' width='500' height='450'>" +
            + "</div>"
            + "<script src='/static/postix/desk/js/games/snake.js' type='text/javascript'></script>");
    },

    '/tetris': function (args) {
        commands._info_view("<script src='/static/postix/desk/js/games/blockrain.js'></script>"
            + "<link rel='stylesheet' href=/static/postix/desk/css/games/blockrain.css>"
            + "<div class='game' style='width:250px; height:500px; margin:auto;'></div>"
            + "<script>"
            + "    $('.game').blockrain({theme: 'candy'});"
            + "    $('.game').blockrain('start');"
            + "</script>");
    },

    '/frogger': function (args) {
        commands._info_view("<script src='/static/postix/desk/js/games/frogger.js'></script>"
            + "<div id='game-div'>"
            + "    <canvas id='game' height='565' width='399'></canvas>"
            + "</div>");
    },

    '/lightcycles': function (args) {
        commands._info_view("<div style='background-color:#FFFFFF;width:500px; height:450px; margin:auto;'>"
            + "    <canvas id='the-game' width='500' height='450'>" +
            + "</div>"
            + "<script src='/static/postix/desk/js/games/lightcycles.js' type='text/javascript'></script>");
    },

    process: function (command) {
        if (command.slice(0, 1) !== "/") {
            command = "/" + command;
        }
        var args = command.split(" ");
        command = args[0];
        if (typeof commands[command] !== 'undefined') {
            commands[command](args);
            return true;
        } else {
            return false;
        }
    },

    init: function () {
        $("#info-view .btn-close").mousedown(function () {
            $("#info-view").hide();
        })
    }

};
