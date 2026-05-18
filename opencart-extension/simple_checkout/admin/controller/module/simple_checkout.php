<?php
namespace Opencart\Admin\Controller\Extension\Simple_checkout\Module;

/**
 * Simple Checkout — install, settings, events.
 */
class SimpleCheckout extends \Opencart\System\Engine\Controller {
	public function index(): void {
		$this->load->language('extension/simple_checkout/module/simple_checkout');

		$this->document->setTitle($this->language->get('heading_title'));

		$data['breadcrumbs'] = [];

		$data['breadcrumbs'][] = [
			'text' => $this->language->get('text_home'),
			'href' => $this->url->link('common/dashboard', 'user_token=' . $this->session->data['user_token'])
		];

		$data['breadcrumbs'][] = [
			'text' => $this->language->get('text_extension'),
			'href' => $this->url->link('marketplace/extension', 'user_token=' . $this->session->data['user_token'] . '&type=module')
		];

		$data['breadcrumbs'][] = [
			'text' => $this->language->get('heading_title'),
			'href' => $this->url->link('extension/simple_checkout/module/simple_checkout', 'user_token=' . $this->session->data['user_token'])
		];

		$data['save'] = $this->url->link('extension/simple_checkout/module/simple_checkout.save', 'user_token=' . $this->session->data['user_token']);
		$data['back'] = $this->url->link('marketplace/extension', 'user_token=' . $this->session->data['user_token'] . '&type=module');

		$data['module_simple_checkout_status'] = (int)$this->config->get('module_simple_checkout_status');

		$data['header'] = $this->load->controller('common/header');
		$data['column_left'] = $this->load->controller('common/column_left');
		$data['footer'] = $this->load->controller('common/footer');

		$this->response->setOutput($this->load->view('extension/simple_checkout/module/simple_checkout', $data));
	}

	public function save(): void {
		$this->load->language('extension/simple_checkout/module/simple_checkout');

		$json = [];

		if (!$this->user->hasPermission('modify', 'extension/simple_checkout/module/simple_checkout')) {
			$json['error'] = $this->language->get('error_permission');
		}

		if (!$json) {
			$this->load->model('setting/setting');
			$this->model_setting_setting->editSetting('module_simple_checkout', $this->request->post);
			$json['success'] = $this->language->get('text_success');
		}

		$this->response->addHeader('Content-Type: application/json');
		$this->response->setOutput(json_encode($json));
	}

	public function install(): void {
		$this->load->model('setting/event');

		$this->model_setting_event->addEvent([
			'code'        => 'simple_checkout_checkout_before',
			'description' => 'Simple Checkout: load frontend script',
			'trigger'     => 'catalog/controller/checkout/checkout/before',
			'action'      => 'extension/simple_checkout/event/simple_checkout.before',
			'status'      => 1,
			'sort_order'  => 0
		]);

		$this->model_setting_event->addEvent([
			'code'        => 'simple_checkout_checkout_after',
			'description' => 'Simple Checkout: expose language on checkout page',
			'trigger'     => 'catalog/controller/checkout/checkout/after',
			'action'      => 'extension/simple_checkout/event/simple_checkout.after',
			'status'      => 1,
			'sort_order'  => 0
		]);
	}

	public function uninstall(): void {
		$this->load->model('setting/event');
		$this->model_setting_event->deleteEventByCode('simple_checkout_checkout_before');
		$this->model_setting_event->deleteEventByCode('simple_checkout_checkout_after');

		$this->load->model('setting/setting');
		$this->model_setting_setting->deleteSetting('module_simple_checkout');
	}
}
