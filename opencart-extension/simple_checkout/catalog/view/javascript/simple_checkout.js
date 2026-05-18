/**
 * Simple Checkout — OpenCart 4.1+
 */
(function () {
    'use strict';

    var root = document.getElementById('checkout-checkout');
    var language = (root && root.dataset.language) ? root.dataset.language : 'en-gb';

    var ROUTES = {
        resolve: 'index.php?route=extension/simple_checkout/checkout/auto.resolve&language=' + language,
        shippingSave: 'index.php?route=checkout/shipping_method.save&language=' + language,
        paymentSave: 'index.php?route=checkout/payment_method.save&language=' + language,
        confirm: 'index.php?route=checkout/confirm.confirm&language=' + language,
        cart: 'index.php?route=common/cart.info&language=' + language
    };

    var ADDRESS_SAVE_ROUTES = [
        'checkout/register.save',
        'checkout/payment_address.save',
        'checkout/shipping_address.save',
        'checkout/payment_address.address',
        'checkout/shipping_address.address'
    ];

    function ajaxCall(options) {
        if (typeof chain !== 'undefined' && chain.attach) {
            chain.attach(function () {
                return $.ajax(options);
            });
            return;
        }
        return $.ajax(options);
    }

    function ensureContainers() {
        var shippingWrap = document.getElementById('checkout-shipping-method');
        if (shippingWrap && !document.getElementById('simple-checkout-shipping')) {
            var sbox = document.createElement('div');
            sbox.id = 'simple-checkout-shipping';
            sbox.className = 'simple-checkout-panel border rounded p-3 mb-3 d-none';
            sbox.innerHTML = '<p class="fw-semibold mb-2"><i class="fa fa-truck"></i> Shipping method</p><div id="simple-checkout-shipping-options"></div>';
            shippingWrap.appendChild(sbox);
        }

        var paymentWrap = document.getElementById('checkout-payment-method');
        if (paymentWrap && !document.getElementById('simple-checkout-payment')) {
            var pbox = document.createElement('div');
            pbox.id = 'simple-checkout-payment';
            pbox.className = 'simple-checkout-panel border rounded p-3 mb-3 d-none';
            pbox.innerHTML = '<p class="fw-semibold mb-2"><i class="fa fa-credit-card"></i> Payment method</p><div id="simple-checkout-payment-options"></div>';
            paymentWrap.insertBefore(pbox, paymentWrap.firstChild);
        }
    }

    function hideChooseButtons() {
        $('#button-shipping-methods, #button-payment-methods').addClass('d-none');
    }

    function setInputValue(id, text, codeId, code) {
        var input = document.getElementById(id);
        var codeInput = document.getElementById(codeId);
        if (input) {
            input.value = text || '';
        }
        if (codeInput) {
            codeInput.value = code || '';
        }
    }

    function refreshConfirm() {
        if ($('#checkout-confirm').length) {
            $('#checkout-confirm').load(ROUTES.confirm);
        }
    }

    function refreshCart() {
        if ($('#cart').length) {
            $('#cart').load(ROUTES.cart);
        }
    }

    function showAlert(type, message) {
        if (!$('#alert').length) {
            return;
        }
        var icon = type === 'success' ? 'fa-circle-check' : 'fa-circle-exclamation';
        $('#alert').prepend(
            '<div class="alert alert-' + type + ' alert-dismissible"><i class="fa-solid ' + icon + '"></i> ' +
            message +
            ' <button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>'
        );
    }

    function renderShippingRadios(shipping_methods, selectedCode) {
        var container = document.getElementById('simple-checkout-shipping-options');
        var panel = document.getElementById('simple-checkout-shipping');
        if (!container || !panel) {
            return;
        }

        var html = '<form id="simple-form-shipping-method">';
        var first = true;

        for (var i in shipping_methods) {
            if (!Object.prototype.hasOwnProperty.call(shipping_methods, i)) {
                continue;
            }
            var ext = shipping_methods[i];
            if (ext.error) {
                html += '<div class="alert alert-danger">' + ext.error + '</div>';
                continue;
            }
            html += '<p class="mb-1"><strong>' + ext.name + '</strong></p>';
            for (var j in ext.quote) {
                if (!Object.prototype.hasOwnProperty.call(ext.quote, j)) {
                    continue;
                }
                var quote = ext.quote[j];
                var rid = 'sc-ship-' + i + '-' + String(j).replaceAll('_', '-');
                var checked = (quote.code === selectedCode) || (!selectedCode && first);
                html += '<div class="form-check">';
                html += '<input class="form-check-input" type="radio" name="shipping_method" value="' + quote.code + '" id="' + rid + '"' + (checked ? ' checked' : '') + '>';
                html += '<label class="form-check-label" for="' + rid + '">' + quote.name + ' - ' + (quote.text || '') + '</label>';
                html += '</div>';
                first = false;
            }
        }

        html += '<div class="text-end mt-2"><button type="submit" class="btn btn-primary btn-sm">Apply shipping</button></div></form>';
        container.innerHTML = html;
        panel.classList.remove('d-none');
    }

    function renderPaymentRadios(payment_methods, selectedCode) {
        var container = document.getElementById('simple-checkout-payment-options');
        var panel = document.getElementById('simple-checkout-payment');
        if (!container || !panel) {
            return;
        }

        var html = '<form id="simple-form-payment-method">';
        var first = true;

        for (var i in payment_methods) {
            if (!Object.prototype.hasOwnProperty.call(payment_methods, i)) {
                continue;
            }
            var ext = payment_methods[i];
            if (ext.error) {
                html += '<div class="alert alert-danger">' + ext.error + '</div>';
                continue;
            }
            html += '<p class="mb-1"><strong>' + ext.name + '</strong></p>';
            for (var j in ext.option) {
                if (!Object.prototype.hasOwnProperty.call(ext.option, j)) {
                    continue;
                }
                var option = ext.option[j];
                var rid = 'sc-pay-' + i + '-' + String(j).replaceAll('_', '-');
                var checked = (option.code === selectedCode) || (!selectedCode && first);
                html += '<div class="form-check">';
                html += '<input class="form-check-input" type="radio" name="payment_method" value="' + option.code + '" id="' + rid + '"' + (checked ? ' checked' : '') + '>';
                html += '<label class="form-check-label" for="' + rid + '">' + option.name + '</label>';
                html += '</div>';
                first = false;
            }
        }

        html += '<div class="text-end mt-2"><button type="submit" class="btn btn-primary btn-sm">Apply payment</button></div></form>';
        container.innerHTML = html;
        panel.classList.remove('d-none');
    }

    function applyResolveResult(json) {
        if (json.error) {
            showAlert('danger', json.error);
            return;
        }

        if (json.shipping) {
            if (json.shipping.auto_selected) {
                setInputValue('input-shipping-method', json.shipping.name, 'input-shipping-code', json.shipping.code);
                document.getElementById('simple-checkout-shipping')?.classList.add('d-none');
            } else if (json.shipping_methods && json.shipping.count > 1) {
                renderShippingRadios(json.shipping_methods, $('#input-shipping-code').val() || '');
            }
        }

        if (json.payment) {
            if (json.payment.auto_selected) {
                setInputValue('input-payment-method', json.payment.name, 'input-payment-code', json.payment.code);
                document.getElementById('simple-checkout-payment')?.classList.add('d-none');
            } else if (json.payment_methods && json.payment.count > 1) {
                renderPaymentRadios(json.payment_methods, $('#input-payment-code').val() || '');
            }
        }

        refreshCart();
        refreshConfirm();
    }

    function resolveMethods() {
        ajaxCall({
            url: ROUTES.resolve,
            dataType: 'json',
            success: function (json) {
                if (json.redirect) {
                    location = json.redirect;
                    return;
                }
                applyResolveResult(json);
            },
            error: function (xhr, _a, thrown) {
                console.error('Simple Checkout resolve failed', thrown, xhr.responseText);
            }
        });
    }

    function afterAddressSaved() {
        ensureContainers();
        hideChooseButtons();
        setInputValue('input-shipping-method', '', 'input-shipping-code', '');
        setInputValue('input-payment-method', '', 'input-payment-code', '');
        resolveMethods();
    }

    function bindAjaxHooks() {
        $(document).ajaxSuccess(function (_event, xhr, settings) {
            if (!settings.url) {
                return;
            }
            var matched = ADDRESS_SAVE_ROUTES.some(function (r) {
                return settings.url.indexOf(r) !== -1;
            });
            if (!matched) {
                return;
            }
            var json = xhr.responseJSON;
            if (json && json.success) {
                afterAddressSaved();
            }
        });

        $(document).on('submit', '#simple-form-shipping-method', function (e) {
            e.preventDefault();
            ajaxCall({
                url: ROUTES.shippingSave,
                type: 'post',
                data: $('#simple-form-shipping-method').serialize(),
                dataType: 'json',
                success: function (json) {
                    if (json.error) {
                        showAlert('danger', json.error);
                        return;
                    }
                    if (json.success) {
                        var label = $('input[name="shipping_method"]:checked').closest('.form-check').find('label').text();
                        var code = $('input[name="shipping_method"]:checked').val();
                        setInputValue('input-shipping-method', label, 'input-shipping-code', code);
                        setInputValue('input-payment-method', '', 'input-payment-code', '');
                        document.getElementById('simple-checkout-shipping')?.classList.add('d-none');
                        resolveMethods();
                    }
                }
            });
        });

        $(document).on('submit', '#simple-form-payment-method', function (e) {
            e.preventDefault();
            ajaxCall({
                url: ROUTES.paymentSave,
                type: 'post',
                data: $('#simple-form-payment-method').serialize(),
                dataType: 'json',
                success: function (json) {
                    if (json.error) {
                        showAlert('danger', json.error);
                        return;
                    }
                    if (json.success) {
                        var label = $('input[name="payment_method"]:checked').closest('.form-check').find('label').text();
                        var code = $('input[name="payment_method"]:checked').val();
                        setInputValue('input-payment-method', label, 'input-payment-code', code);
                        document.getElementById('simple-checkout-payment')?.classList.add('d-none');
                        refreshConfirm();
                    }
                }
            });
        });
    }

    function init() {
        if (typeof $ === 'undefined') {
            return;
        }
        ensureContainers();
        hideChooseButtons();
        bindAjaxHooks();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
