<?php
namespace Opencart\Catalog\Controller\Extension\Simple_checkout\Event;

/**
 * Checkout page hooks for Simple Checkout.
 */
class SimpleCheckout extends \Opencart\System\Engine\Controller {
	public function before(string &$route, array &$args): void {
		if (!(int)$this->config->get('module_simple_checkout_status')) {
			return;
		}

		$this->document->addScript('extension/simple_checkout/catalog/view/javascript/simple_checkout.js', 'footer');
	}

	public function after(string &$route, array &$args, mixed &$output): void {
		if (!(int)$this->config->get('module_simple_checkout_status')) {
			return;
		}

		$language = (string)$this->config->get('config_language');

		$output = str_replace(
			'id="checkout-checkout"',
			'id="checkout-checkout" data-language="' . htmlspecialchars($language, ENT_QUOTES, 'UTF-8') . '"',
			$output
		);
	}
}
