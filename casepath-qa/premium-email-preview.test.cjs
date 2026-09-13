'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const view=require('../casepath/assets/claims-workspace-presentation-v1.js');
test('plain email body is readable and exact original headers remain inspectable',()=>{
 const body='I paid before the notice.\r\nPlease check the receipt.';
 const raw='From: claimant@example.invalid\r\nSubject: Payment receipt\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n'+body;
 const html=view.textSourceMarkup(raw,'message/rfc822');
 assert.ok(html.includes('>'+body+'</div>'));assert.match(html,/Email headers/);
 assert.match(html,/From: claimant@example.invalid/);assert.match(html,/tabindex="0"/);
});
test('markup embedded in a message is text, never active content',()=>{
 const html=view.textSourceMarkup('Subject: check\n\n<script>alert(1)</script>','message/rfc822');
 assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/<script>/);
});
test('an encoded or multipart email is preserved without pretending to decode it',()=>{
 const raw='Content-Type: multipart/mixed; boundary=x\n\n--x\nContent-Transfer-Encoding: base64\n\nYWJj';
 const html=view.textSourceMarkup(raw,'message/rfc822');
 assert.match(html,/Original email source/);assert.ok(html.includes(view.h(raw)));
});
test('other source text remains byte-faithful after decoding and HTML escaping',()=>{
 assert.match(view.textSourceMarkup('<b>Receipt</b>','text/plain'),/&lt;b&gt;Receipt&lt;\/b&gt;/);
});
