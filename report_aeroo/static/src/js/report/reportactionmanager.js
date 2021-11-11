/** @odoo-module **/

import {download} from "@web/core/network/download"
import {registry} from "@web/core/registry"

async function aerooReportHandler (action, options, env){
    let cloned_action = _.clone(action);
    if (action.report_type === "aeroo"){
        const type = "aeroo";
        let url_ = `/report/${type}/${action.report_name}`;
        const actionContext = action.context || {};
        if (cloned_action.context.active_ids) {
            url_ += "/" + cloned_action.context.active_ids.join(',');
            // odoo does not send context if no data, but I find it quite useful to send it regardless data or no data
            url_ += "?context=" + encodeURIComponent(JSON.stringify(cloned_action.context));
        } else {
            url_ += "?options=" + encodeURIComponent(JSON.stringify(cloned_action.data));
            url_ += "&context=" + encodeURIComponent(JSON.stringify(cloned_action.context));
        }
        if (action.data && JSON.stringify(action.data) !== "{}") {
            const options_ = encodeURIComponent(JSON.stringify(action.data));
            const context_ = encodeURIComponent(JSON.stringify(actionContext));
            url_ += `?options=${options_}&context=${context_}`;
        } else {
            if (actionContext.active_ids) {
                url_ += `/${actionContext.active_ids.join(",")}`;
            }
            if (type === "html") {
                const context = encodeURIComponent(
                    JSON.stringify(env.services.user.context)
                );
                url_ += `?context=${context}`;
            }
        }
        // COPY actionManager._triggerDownload
        env.services.ui.block();
        try {
            await download({
                url: "/report/download",
                data: {
                    data: JSON.stringify([url_, action.report_type]),
                    context: JSON.stringify(env.services.user.context),
                },
            });
        } finally {
            env.services.ui.unblock();
        }
        const onClose = options.onClose;
        if (action.close_on_report_download) {
            return env.services.action.doAction(
                {type: "ir.actions.act_window_close"},
                {onClose}
            );
        } else if (onClose) {
            onClose();
        }
        // DIFF: need to inform success to the original method. Otherwise it
        // will think our hook function did nothing and run the original
        // method.
        return Promise.resolve(true);
    }
}

registry.category("ir.actions.report handlers").add("aeroo_handler", aerooReportHandler);



/* odoo.define("report_aeroo.report", function (require) {
    "use strict";

    var core = require("web.core");
    var ActionManager = require("web.ActionManager");
    var framework = require("web.framework");
    var session = require("web.session");
    var _t = core._t;

    ActionManager.include({

        _downloadReportAEROO: function (url, actions) {
            framework.blockUI();
            var self = this;
            var type = "aeroo";
            var new_url = url;
            var cloned_action = _.clone(actions);

            if (cloned_action.context.active_ids) {
                new_url += "/" + cloned_action.context.active_ids.join(',');
                // odoo does not send context if no data, but I find it quite useful to send it regardless data or no data
                new_url += "?context=" + encodeURIComponent(JSON.stringify(cloned_action.context));
            } else {
                new_url += "?options=" + encodeURIComponent(JSON.stringify(cloned_action.data));
                new_url += "&context=" + encodeURIComponent(JSON.stringify(cloned_action.context));
            }
            // esto es mas parecido a en otros modulos pero hace que, por ej, nuestro reporte de deuda deje de funcionar
            // if (_.isUndefined(cloned_action.data) ||
            //     _.isNull(cloned_action.data) ||
            //     (_.isObject(cloned_action.data) && _.isEmpty(cloned_action.data)))
            // {
            //     if (cloned_action.context.active_ids) {
            //         new_url += "/" + cloned_action.context.active_ids.join(',');
            //         // odoo does not send context if no data, but I find it quite useful to send it regardless data or no data
            //         new_url += "?context=" + encodeURIComponent(JSON.stringify(cloned_action.context));
            //     }
            // } else {
            //     new_url += "?options=" + encodeURIComponent(JSON.stringify(cloned_action.data));
            //     new_url += "&context=" + encodeURIComponent(JSON.stringify(cloned_action.context));
            // }

            return new Promise(function (resolve, reject) {
                var blocked = !session.get_file({
                    url: new_url,
                    data: {
                        data: JSON.stringify([new_url, type]),
                    },
                    success: resolve,
                    error: (error) => {
                        self.call('crash_manager', 'rpc_error', error);
                        reject();
                    },
                    complete: framework.unblockUI,
                });
                if (blocked) {
                    // AAB: this check should be done in get_file service directly,
                    // should not be the concern of the caller (and that way, get_file
                    // could return a deferred)
                    var message = _t('A popup window with your report was blocked. You ' +
                                     'may need to change your browser settings to allow ' +
                                     'popup windows for this page.');
                    this.do_warn(_t('Warning'), message, true);
                }
            });
        },

        _triggerDownload: function (action, options, type) {
            var self = this;
            var reportUrls = this._makeReportUrls(action);
            if (type === "aeroo") {
                return this._downloadReportAEROO(reportUrls[type], action).then(function () {
                    if (action.close_on_report_download) {
                        var closeAction = {type: 'ir.actions.act_window_close'};
                        return self.doAction(closeAction, _.pick(options, 'on_close'));
                    } else {
                        return options.on_close();
                    }
                });
            }
            return this._super.apply(this, arguments);
        },

        _makeReportUrls: function (action) {
            var reportUrls = this._super.apply(this, arguments);
            reportUrls.aeroo = '/report/aeroo/' + action.report_name;
            return reportUrls;
        },

        _executeReportAction: function (action, options) {
            debugger;
            var self = this;
            if (action.report_type === 'aeroo') {
                return self._triggerDownload(action, options, 'aeroo');
            }
            return this._super.apply(this, arguments);
        }
    });

});
 */
