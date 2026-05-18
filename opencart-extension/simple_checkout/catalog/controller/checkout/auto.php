<?php
namespace Opencart\Catalog\Controller\Extension\Simple_checkout\Checkout;

/**
 * Resolves shipping and payment in one request; auto-saves when only one option exists.
 */
class Auto extends \Opencart\System\Engine\Controller {
	public function resolve(): void {
		$this->load->language('checkout/checkout');

		$json = [];

		if (!$this->cart->hasProducts() || (!$this->cart->hasStock() && !$this->config->get('config_stock_checkout')) || !$this->cart->hasMinimum()) {
			$json['redirect'] = $this->url->link('checkout/cart', 'language=' . $this->config->get('config_language'), true);
		}

		if (!$json && !isset($this->session->data['customer'])) {
			$json['error'] = $this->language->get('error_customer');
		}

		if (!$json && $this->config->get('config_checkout_payment_address') && !isset($this->session->data['payment_address'])) {
			$json['error'] = $this->language->get('error_payment_address');
		}

		if (!$json && $this->cart->hasShipping() && !isset($this->session->data['shipping_address']['address_id'])) {
			$json['error'] = $this->language->get('error_shipping_address');
		}

		$json['shipping'] = ['resolved' => false, 'count' => 0, 'auto_selected' => false];
		$json['payment'] = ['resolved' => false, 'count' => 0, 'auto_selected' => false];

		if (!$json && $this->cart->hasShipping()) {
			$this->load->model('checkout/shipping_method');

			$shipping_methods = $this->model_checkout_shipping_method->getMethods($this->session->data['shipping_address']);

			if (!$shipping_methods) {
				$json['error'] = sprintf($this->language->get('error_no_shipping'), $this->url->link('information/contact', 'language=' . $this->config->get('config_language')));
			} else {
				$this->session->data['shipping_methods'] = $shipping_methods;
				$quotes = $this->flattenShippingQuotes($shipping_methods);
				$json['shipping']['count'] = count($quotes);
				$json['shipping_methods'] = $shipping_methods;

				if (count($quotes) === 1) {
					$this->session->data['shipping_method'] = $quotes[0]['quote'];
					unset($this->session->data['payment_method'], $this->session->data['payment_methods']);
					$json['shipping']['auto_selected'] = true;
					$json['shipping']['code'] = $quotes[0]['quote']['code'];
					$json['shipping']['name'] = $quotes[0]['quote']['name'] . (isset($quotes[0]['quote']['text']) ? ' - ' . $quotes[0]['quote']['text'] : '');
				}

				$json['shipping']['resolved'] = isset($this->session->data['shipping_method']);
			}
		} elseif (!$json) {
			$json['shipping']['resolved'] = true;
		}

		if (!$json && (!$this->cart->hasShipping() || isset($this->session->data['shipping_method']))) {
			$payment_address = [];

			if ($this->config->get('config_checkout_payment_address') && isset($this->session->data['payment_address'])) {
				$payment_address = $this->session->data['payment_address'];
			} elseif ($this->config->get('config_checkout_shipping_address') && isset($this->session->data['shipping_address']['address_id'])) {
				$payment_address = $this->session->data['shipping_address'];
			}

			$this->load->model('checkout/payment_method');

			$payment_methods = $this->model_checkout_payment_method->getMethods($payment_address);

			if (!$payment_methods) {
				$json['error'] = sprintf($this->language->get('error_no_payment'), $this->url->link('information/contact', 'language=' . $this->config->get('config_language')));
			} else {
				$this->session->data['payment_methods'] = $payment_methods;
				$options = $this->flattenPaymentOptions($payment_methods);
				$json['payment']['count'] = count($options);
				$json['payment_methods'] = $payment_methods;

				if (count($options) === 1) {
					$this->session->data['payment_method'] = $options[0]['option'];
					$json['payment']['auto_selected'] = true;
					$json['payment']['code'] = $options[0]['option']['code'];
					$json['payment']['name'] = $options[0]['option']['name'];
				}

				$json['payment']['resolved'] = isset($this->session->data['payment_method']);
			}
		}

		$this->response->addHeader('Content-Type: application/json');
		$this->response->setOutput(json_encode($json));
	}

	/**
	 * @param array<string, array<string, mixed>> $shipping_methods
	 * @return list<array{quote: array<string, mixed>}>
	 */
	private function flattenShippingQuotes(array $shipping_methods): array {
		$quotes = [];

		foreach ($shipping_methods as $extension) {
			if (!empty($extension['error']) || empty($extension['quote'])) {
				continue;
			}

			foreach ($extension['quote'] as $quote) {
				if (!empty($quote['code'])) {
					$quotes[] = ['quote' => $quote];
				}
			}
		}

		return $quotes;
	}

	/**
	 * @param array<string, array<string, mixed>> $payment_methods
	 * @return list<array{option: array<string, mixed>}>
	 */
	private function flattenPaymentOptions(array $payment_methods): array {
		$options = [];

		foreach ($payment_methods as $extension) {
			if (!empty($extension['error']) || empty($extension['option'])) {
				continue;
			}

			foreach ($extension['option'] as $option) {
				if (!empty($option['code'])) {
					$options[] = ['option' => $option];
				}
			}
		}

		return $options;
	}
}
