
  //Обробник кнопки Готово для відправки даних по додаванню сервера та double add check
  // Глобальні змінні для форми додавання сервера
  const addServerButton = document.getElementById('add-server-button');
  const gameSelect = document.getElementById('game-name-select');
  const regionSelect = document.getElementById('region-select');
  const serverSelect = document.getElementById('server-select');
  const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
  const form = document.getElementById('close-add-server-form');

  //Функція перевірки існування сервера в таблиці
  function isServerExists(formData, existingServers) {
  return existingServers.some(existingServer =>
    existingServer.server_name === formData.server &&
    existingServer.game_name === formData.game
  );
  }

  // Обробник кнопки "Готово"
  addServerButton.addEventListener('click', (event) => {
    event.preventDefault();


  const formData = {
    game: gameSelect.value,
    region: regionSelect.value,
    server: serverSelect.value,
  };

  // Список існуючих серверів
  const existingServers = {{ double_add | safe }};

      // Перевіряємо, чи сервер уже доданий
  if (isServerExists(formData, existingServers)) {
    alert('Цей сервер вже існує в таблиці.');
    return;
  }


   fetch("{% url 'main:add_server' %}", {
    method: 'POST',
    headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': csrfToken
  },
  body: JSON.stringify(formData)
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        // Відображаємо модальне вікно
        // Перезавантажуємо сторінку
        window.location.reload();
      }
    })
    .catch((error) => {
      console.error('Error:', error);
      alert('Сталася несподівана помилка. Будь ласка, спробуйте пізніше.');
    });
  });



  // Динамічна зміна списку серверів в залежності від вибору гри та регіону
  const gameSelectAdd = document.getElementById('game-name-select');
  const regionSelectAdd = document.getElementById('region-select');

  function updateServers(game, region) {
    const serversData = {{ servers_json | safe }};
    const selectedServers = serversData[game]?.[region] || [];
    serverSelect.innerHTML = '';

    selectedServers.forEach((server) => {
      const option = document.createElement('option');
      option.value = server;
      option.textContent = server;
      serverSelect.appendChild(option);
    });
  }

  gameSelectAdd.addEventListener('change', () => {
    updateServers(gameSelectAdd.value, regionSelect.value);
  });

  regionSelectAdd.addEventListener('change', () => {
    updateServers(gameSelectAdd.value, regionSelectAdd.value);
  });

  // Ініціалізація
  updateServers(gameSelect.value, regionSelectAdd.value);



  // Обробник кнопки Додати сервер для появи форми
  // Унікальна функція для управління відображенням форми
  const toggleAddServerForm = document.querySelector('.save-button:first-child');
  const addServerForm = document.getElementById('add-server-form');

  toggleAddServerForm.addEventListener('click', () => {
    addServerForm.style.display = addServerForm.style.display === 'none' ? 'block' : 'none';
  });


  // Динамічна зміна ціни та перевірка зміни значення "stock"
  const tableRows = document.querySelectorAll('tr:not(#add-server-body):not(#add-server-head)');
  const csrftoken = document.cookie.split(';')
    .map(c => c.trim())
    .find(c => c.startsWith('csrftoken='))
    ?.split('=')[1];

  if (!csrftoken) {
    console.error('CSRF token not found!');
  }

  // Validation function for numeric input
  function isNumberKey(event) {
    const charCode = event.which ? event.which : event.keyCode;
    // Allow numbers (0-9), period (.), and backspace
    if (
      charCode !== 46 && // Allow '.'
      (charCode < 48 || charCode > 57) && // Allow '0-9'
      charCode !== 8 // Allow backspace
    ) {
      return false;
    }
    return true;
  }

  // Validate and format stock input
  function validateStock(input) {
    const stockValue = input.value;
    const regex = /^\d+(\.\d{1,2})?$/; // Allow numbers with up to 2 decimal places

    if (!regex.test(stockValue)) {
      alert('Please enter a valid number (e.g., 10, 10.5)');
      input.value = ''; // Clear invalid input
    }
  }

  tableRows.forEach(row => {
    const inputs = row.querySelectorAll('input, select.strategy-select');

    inputs.forEach(input => {
      // Add keypress validation for numeric inputs
      if (input.name === 'stock') {
        input.addEventListener('keypress', isNumberKey);
        input.addEventListener('blur', () => validateStock(input));
      }

      // Listen for changes to update data dynamically
      input.addEventListener('change', () => {
        const rowId = row.id;
        const fieldName = input.name;
        const newValue = input.value;

        console.log(`Detected change - Row ID: ${rowId}, Field: ${fieldName}, New Value: ${newValue}`);

        const data = {
          row_id: rowId,
          field_name: fieldName,
          new_value: newValue,
        };

        fetch("{% url 'main:update_table_data' %}", {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken,
          },
          body: JSON.stringify(data),
        })
          .then(response => response.json())
          .then(data => {
            console.log('Server response:', data);

            if (data.success) {
              const priceInputId = `price-field-${rowId}`;
              const priceInput = document.querySelector(`#${priceInputId}`);
              if (priceInput) {
                console.log(`Updating price in row ID ${rowId} with new value: ${data.new_price}`);
                priceInput.value = data.new_price;
              } else {
                console.warn(`Price field not found in row ID: ${rowId}`);
              }
            } else {
              console.error('Failed to update data:', data);
            }
          })
          .catch(error => {
            console.error('Fetch request error:', error);
          });
      });
    });
  });


document.addEventListener('DOMContentLoaded', function() {
    // Отримуємо посилання на елементи форми та кнопки
    const addServerFormForClose = document.getElementById('add-server-form');
    const closeAddServerFormButton = document.getElementById('close-add-server-form');

    // Додаємо обробник події для кнопки "Скасувати"
    closeAddServerFormButton.addEventListener('click', function() {
        // Приховуємо форму
        addServerFormForClose.style.display = 'none';
    });

});
  //Призупинення та видалення лотів
  document.addEventListener('DOMContentLoaded', () => {
  // Відслідковуємо зміну в select
  const selectElements = document.querySelectorAll('.select-options');

  selectElements.forEach((selectElement) => {
    selectElement.addEventListener('change', (event) => {
      const selectedOption = event.target.value; // Отримуємо вибраний варіант
      const rowId = event.target.id.split('-').pop(); // Отримуємо ID рядка з ID елемента

      // Якщо вибраний варіант не порожній
      if (selectedOption !== 'emtpy-field') {
        // Створюємо модальне вікно підтвердження
        const modal = document.createElement('div');
        modal.classList.add('modal');
        modal.innerHTML = `
          <div class="modal-overlay"></div>
          <div class="modal-content">
            <p>Ви дійсно хочете ${
                selectedOption === 'pause'
                  ? 'зупинити продаж'
                  : selectedOption === 'delete'
                  ? 'видалити сервер'
                  : 'відновити продаж'
              }?</p>
            <button id="confirm-button" class="btn">Так</button>
            <button id="cancel-button" class="btn btn-cancel">Ні</button>
          </div>
        `;
        document.body.appendChild(modal);

        // Додаємо стилі для модального вікна
        addModalStyles();

        // Обробка натискання кнопки "Так"
        const confirmButton = document.getElementById('confirm-button');
        confirmButton.addEventListener('click', () => {
          modal.remove(); // Закриваємо модальне вікно

          // Надсилаємо дані на сервер
          const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
          fetch("{% url 'main:handle_option_change' %}", {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify({ row_id: rowId, action: selectedOption }),
          })
            .then((response) => response.json())
            .then((data) => {
              if (data.success) {
                // Перезавантажуємо сторінку
                window.location.reload();
                console.log('Операцію успішно виконано:', data.message);
              } else {
                console.error('Помилка:', data.error);
              }
            })
            .catch((error) => console.error('Помилка запиту:', error));
        });

        // Обробка натискання кнопки "Ні"
        const cancelButton = document.getElementById('cancel-button');
        cancelButton.addEventListener('click', () => {
          modal.remove(); // Закриваємо модальне вікно
          event.target.value = 'emtpy-field'; // Скидаємо вибір
        });
      }
    });
  });

  // Функція для додавання стилів модального вікна
  function addModalStyles() {
    const style = document.createElement('style');
    style.innerHTML = `
      .modal {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        display: flex;
        justify-content: center;
        align-items: center;
        background-color: rgba(0, 0, 0, 0.5);
        z-index: 1000;
      }
      .modal-overlay {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0, 0, 0, 0.5);
      }
      .modal-content {
        position: relative;
        background: white;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
        text-align: center;
        z-index: 1001;
      }
      .modal-content .btn {
        margin: 10px;
        padding: 10px 20px;
        background-color: #007bff;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
      }
      .modal-content .btn-cancel {
        background-color: #dc3545;
      }
      .modal-content .btn:hover {
        background-color: #0056b3;
      }
      .modal-content .btn-cancel:hover {
        background-color: #c82333;
      }
    `;
    document.head.appendChild(style);
  }
});
